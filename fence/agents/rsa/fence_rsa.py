#!/usr/bin/python

import getopt, sys
import os
import socket
import time

from telnetlib import Telnet

TELNET_TIMEOUT=30  #How long to wait for a response from a telnet try

# WARNING!! Do not add code bewteen "#BEGIN_VERSION_GENERATION" and
# "#END_VERSION_GENERATION"  It is generated by the Makefile

#BEGIN_VERSION_GENERATION
RELEASE_VERSION=""
REDHAT_COPYRIGHT=""
BUILD_DATE=""
#END_VERSION_GENERATION

def usage():
  print "Usage:"
  print "fence_rsa [options]"
  print "Options:"
  print "   -a <ipaddress>           ip or hostname of rsa II port"
  print "   -h                       print out help"
  print "   -l [login]               login name"
  print "   -p [password]            password"
  print "   -S [path]                script to run to retrieve password"
  print "   -o [action]              reboot (default), off, on, or status"
  print "   -v Verbose               Verbose mode"
  print "   -V                       Print Version, then exit"
  
  sys.exit (0)

def version():
  print "fence_rsa %s  %s\n" % (RELEASE_VERSION, BUILD_DATE)
  print "%s\n" % REDHAT_COPYRIGHT
  sys.exit(0)

def main():

  POWER_OFF = 0
  POWER_ON = 1
  POWER_STATUS = 2
  POWER_REBOOT = 3

  address = ""
  login = ""
  passwd = ""
  passwd_script = ""
  action = POWER_REBOOT   #default action
  verbose = False

  standard_err = 2

  #set up regex list
  USERNAME = 0
  PASSWORD = 1
  PROMPT = 2
  STATE = 3
  ERROR = 4
  regex_list = list()
  regex_list.append("username:")
  regex_list.append("password:")
  regex_list.append(".*>")
  regex_list.append("Power:")
  regex_list.append("Error:")

  if len(sys.argv) > 1:
    try:
      opts, args = getopt.getopt(sys.argv[1:], "a:hl:o:p:S:vV", ["help", "output="])
    except getopt.GetoptError:
      #print help info and quit
      usage()
      sys.exit(2)

                                                                                
    for o, a in opts:
      if o == "-v":
        verbose = True
      if o == "-V":
        version()
      if o in ("-h", "--help"):
        usage()
        sys.exit(0)
      if o == "-l":
        login = a
      if o == "-p":
        passwd = a
      if o == "-S":
        passwd_script = a
      if o  == "-o":
        a_lower=a.lower()
        if a_lower == "off":
          action = POWER_OFF
        elif a_lower == "on":
          action = POWER_ON
        elif a_lower == "status":
          action = POWER_STATUS
        elif a_lower == "reboot":
          action = POWER_REBOOT
        else:
          usage()
          sys.exit(1)
      if o == "-a":
        address = a
    if address == "" or login == "" or (passwd == "" and passwd_script == ""):
      usage()
      sys.exit(1)

  else: #Take args from stdin...
    params = {}
    #place params in dict
    for line in sys.stdin:
      val = line.split("=")
      if len(val) == 2:
        params[val[0].strip()] = val[1].strip()
    
    try:
      address = params["ipaddr"]
    except KeyError, e:
      os.write(standard_err, "FENCE: Missing ipaddr param for fence_rsa...exiting")
      sys.exit(1)
    
    try:
      login = params["login"]
    except KeyError, e:
      os.write(standard_err, "FENCE: Missing login param for fence_rsa...exiting")
      sys.exit(1)
    
    try:
      if 'passwd' in params:
        passwd = params["passwd"]
      if 'passwd_script' in params:
        passwd_script = params['passwd_script']
      if passwd == "" and passwd_script == "":
        raise "missing password"
    except KeyError, e:
      os.write(standard_err, "FENCE: Missing passwd param for fence_rsa...exiting")
      sys.exit(1)
    
    try:
      a = params["option"]
      a_lower=a.lower()
      if a_lower == "off":
        action = POWER_OFF
      elif a_lower == "on":
        action = POWER_ON
      elif a_lower == "reboot":
        action = POWER_REBOOT
    except KeyError, e:
      action = POWER_REBOOT
    
    ####End of stdin section
  
  
  # retrieve passwd from passwd_script (if specified)
  passwd_scr = ''
  if len(passwd_script):
    try:
      if not os.access(passwd_script, os.X_OK):
        raise 'script not executable'
      p = os.popen(passwd_script, 'r', 1024)
      passwd_scr = p.readline().strip()
      if p.close() != None:
        raise 'script failed'
    except:
      sys.stderr.write('password-script "%s" failed\n' % passwd_script)
      passwd_scr = ''
  
  if passwd == "" and passwd_scr == "":
    sys.stderr.write('password not available, exiting...')
    sys.exit(1)
  elif passwd == passwd_scr:
    pass
  elif passwd and passwd_scr:
    # execute self, with password_scr as passwd,
    # if that fails, continue with "passwd" argument as password
    if len(sys.argv) > 1:
      comm = sys.argv[0]
      skip_next = False
      for w in sys.argv[1:]:
        if skip_next:
          skip_next = False
        elif w in ['-p', '-S']:
          skip_next = True
        else:
          comm += ' ' + w
      comm += ' -p ' + passwd_scr
      ret = os.system(comm)
      if ret != -1 and os.WIFEXITED(ret) and os.WEXITSTATUS(ret) == 0:
        # success
        sys.exit(0)
      else:
        sys.stderr.write('Use of password from "passwd_script" failed, trying "passwd" argument\n')
    else: # use stdin
      p = os.popen(sys.argv[0], 'w', 1024)
      for par in params:
        if par not in ['passwd', 'passwd_script']:
          p.write(par + '=' + params[par] + '\n')
      p.write('passwd=' + passwd_scr + '\n')
      p.flush()
      if p.close() == None:
        # success
        sys.exit(0)
      else:
        sys.stderr.write('Use of password from "passwd_script" failed, trying "passwd" argument\n')
  elif passwd_scr:
    passwd = passwd_scr
  # passwd all set
  
  
  
  ##Time to open telnet session and log in. 
  try:
    sock = Telnet(address.strip())
  except socket.error, (errno, msg):
    my_msg = "FENCE: A problem was encountered opening a telnet session with " + address
    os.write(standard_err, my_msg)
    os.write(standard_err, ("FENCE: Error number: %d -- Message: %s\n" % (errno, msg)))
    os.write(standard_err, "Firewall issue? Correct address?\n")
    sys.exit(1)

  if verbose:
    print  "socket open to %s\n" % address

  ##This loop offers all expected responses in the regex_list, and
  ##handles responses accordingly.
  while 1:
    i, mo, txt = sock.expect(regex_list, TELNET_TIMEOUT)
    if i == ERROR:
      os.write(standard_err,("FENCE: An error was encountered when communicating with the rsa device at %s" % address))
      buf = sock.read_eager()
      os.write(standard_err,("FENCE: The error message is - %s" % txt + " " + buf))
      sock.close()
      sys.exit(1)
    if i == USERNAME:
      if verbose:
        print "Sending login: %s\n" % login
      sock.write(login + "\r")
    elif i == PASSWORD:
      if verbose:
        print "Sending password: %s\n" % passwd
      sock.write(passwd + "\r")
    elif i == PROMPT:
      if verbose:
        print "Evaluating prompt...%s\n" % txt
      if action == POWER_OFF:
        if verbose:
          print "Sending power off command to %s\n" % address
        sock.write("power off\r")
        time.sleep(2)
        if verbose:
          buf = sock.read_eager()
          print "result from power off command is: %s" % buf
        break
      if action == POWER_ON:
        if verbose:
          print "Sending power on %s" % address
        sock.write("power on\r")
        time.sleep(2)
        break
      if action == POWER_STATUS:
        if verbose:
          print "Checking power state..."
        sock.write("power state\r")
        time.sleep(2)
      if action == POWER_REBOOT:
        if verbose:
          print "Rebooting server..."
        sock.write("power cycle\r")
        time.sleep(2)
        break
    elif i == STATE:
      power_state = sock.read_until("State:")
      if power_state.find(" On") != (-1):
        print "Server is On"
      elif power_state.find(" Off") != (-1):
        print "Server is off"
      break

  sock.close()

if __name__ == "__main__":
  main()
