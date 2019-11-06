import subprocess
import time

def run_shell_command(command):
#	out = commands.getoutput(command)
	process = subprocess.Popen(command, stdout=subprocess.PIPE,
	                                    stderr=subprocess.PIPE, shell=True)
	time.sleep(2)
	out, err = process.communicate()
	time.sleep(2)
	process.wait()
	return out
