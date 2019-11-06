import json, socket, datetime, traceback

HOST = "localhost"
PORT = 8080

## data -> dict()
def log_event(data):
	if not 'time' in data:
		time_now = datetime.datetime.utcnow().strftime("%Y-%m-%d.%X")
		data['time'] = time_now

	try:
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		msg = json.dumps(data)
		s.connect((HOST, PORT))
		s.send(msg)
		s.close()
	except:
		print(traceback.format_exc())
