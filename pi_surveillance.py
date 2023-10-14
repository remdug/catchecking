from pyimagesearch.tempimage import TempImage
from picamera.array import PiRGBArray
from picamera2 import Picamera2
from email.message import EmailMessage
import smtplib
import mimetypes
import argparse
import warnings
import datetime
import imutils
import json
import time
import cv2

def sendEmail(attachment, time):
	conf = json.load(open(args["conf"]))
	msg = EmailMessage()
	msg["From"] = conf["gmail_username"]
	msg["Subject"] = "capture - %04d%02d%02d-%02d%02d%02d" % (time.year, time.month, time.day, time.hour, time.minute, time.second)
	msg["To"] = conf["gmail_username"]
	msg.set_content("image capturé - mouvement détecté")
   
	with open(attachment, "rb") as fp:
		file_data = fp.read()
		maintype, _, subtype = (mimetypes.guess_type(attachment)[0] or 'application/octet-stream').partition("/")
		msg.add_attachment(file_data, maintype=maintype, subtype=subtype, filename= attachment)
	   
	session = smtplib.SMTP(conf["smtp_server"], conf["smtp_port"])

	session.ehlo()
	session.starttls()
	session.ehlo()

	session.login(conf["gmail_username"], conf["gmail_password"])
	session.send_message(msg)
	print("mail envoyé : %s" % attachment)
	session.quit

ap = argparse.ArgumentParser()
ap.add_argument("-c", "--conf", required=True, help="path to the JSON config file")
args = vars(ap.parse_args())

warnings.filterwarnings("ignore")
conf = json.load(open(args["conf"]))
client = None

camera = Picamera2()
camera.resolution = tuple(conf["resolution"])
camera.framerate = conf["fps"]
rawCapture = PiRGBArray(camera, size=tuple(conf["resolution"]))

print("[INFO] warming up...")
time.sleep(conf["camera_warmup_time"])
avg = None
lastUploaded = datetime.datetime.now()
motionCounter = 0

camera.start()

#for f in camera.capture_continuous(rawCapture, format="bgr", use_video_port=True):
"""for f in camera.capture_array():
	print("[INFO] boucle array")
	frame = f.array
	timestamp = datetime.datetime.now()
	text = "Unoccupied"
	
	frame = imutils.resize(frame, width=500)"""
while True:
	timestamp = datetime.datetime.now()
	text = "Unoccupied"
	frame = camera.capture_array()
	
	#frame = imutils.resize(frame, width=500)
	
	gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
	gray = cv2.GaussianBlur(gray, (21,21), 0)
	
	if avg is None:
		print("[INFO] starting background model...")
		avg = gray.copy().astype("float")
		rawCapture.truncate(0)
		continue
		
	cv2.accumulateWeighted(gray, avg, 0.5)
	frameDelta = cv2.absdiff(gray, cv2.convertScaleAbs(avg))
		
	thresh = cv2.threshold(frameDelta, conf["delta_thresh"], 255, cv2.THRESH_BINARY)[1]
	thresh = cv2.dilate(thresh, None, iterations=2)
	cnts = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
	cnts = imutils.grab_contours(cnts)
	
	for c in cnts:
		if cv2.contourArea(c) < conf["min_area"]:
			continue
		
		(x,y,w,h) = cv2.boundingRect(c)
		cv2.rectangle(frame, (x,y), (x+w, y+h), (0, 255, 0), 2)
		text = "Occupied"
		
	ts = timestamp.strftime("%A %d %B %Y %I:%M:%S%p")
	cv2.putText(frame, "Room Status: {}".format(text), (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 2)
	cv2.putText(frame, ts, (10, frame.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0,255,0), 1)
	
	if text == "Occupied":
		if(timestamp - lastUploaded).seconds >= conf["min_upload_seconds"]:
			motionCounter += 1
			
			if motionCounter >= conf["min_motion_frames"]:
				t = TempImage()
				cv2.imwrite(t.path, frame)
				
				sendEmail(t.path, timestamp)
				t.cleanup()
				
				lastUploaded = timestamp
				motionCounter = 0
			
	else:
		motionCounter = 0
		

		
