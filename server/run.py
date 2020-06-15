import time
import sys
import os

import io
import threading
import picamera

import Adafruit_DHT
import spidev

from flask import Flask, render_template, Response, send_from_directory
app = Flask(__name__)

spi = spidev.SpiDev()
spi.open(0,0)
spi.max_speed_hz=1000000

# Иконка вкладки браузера

@app.route('/favicon.ico') 
def favicon(): 
    return send_from_directory(os.path.join( app.root_path,  'static'), 
                               'favicon.ico',  mimetype= 'image/vnd.microsoft.icon')

# Вывод датчиков почвы
def ReadChannel(channel):
    adc = spi.xfer2([1,(8+channel)<<4,0])
    data = ((adc[1]&3) << 8) + adc[2]
    return data

def getCPSMdata():
    quant = 0
    sum_level = 0
    for i in range(8):
        level = ReadChannel(i-1)
        if level > 0:
            sum_level = sum_level + level
            quant += 1

    if quant != 0:
        level = sum_level / quant
        hum = 100-((level * 100) / float(1023))
        hum  = round(hum ,1)
        hum_soil = hum
        return hum_soil

# Вывод датчиков DHT

def getDHTdata(): 
    DHT22Sensor = Adafruit_DHT.DHT22
    DHTpin = 2
    hum, temp = Adafruit_DHT.read_retry(DHT22Sensor, DHTpin)
    
    if hum is not None and temp is not None:
        hum = round(hum)
        temp = round(temp, 1)
    return temp, hum

# Настройки

@app.route('/settings')
def settings():
    return render_template('settings.html',)

# Вывод датчиков в HTML

@app.route("/")
def index():
    timeNow = time.asctime( time.localtime(time.time()) )
    temp, hum = getDHTdata()
    hum_soil = getCPSMdata()
    
    templateData = {
    'time'    : timeNow,
    'temp'    : temp,
    'hum'     : hum,
    'hum_soil': hum_soil
    }
    
    return render_template('index.html', **templateData)

# Трансляция Web-камеры

@app.route('/camera')
def cam():
    return render_template('index.html')

def gen(camera):
    while True:
        frame = camera.get_frame()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(gen(Camera()),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

# Pi-camera

class Camera(object):
    thread = None
    frame = None
    last_access = 0
    
    def initialize(self):
        if Camera.thread is None:
            Camera.thread = threading.Thread(target=self._thread)
            Camera.thread.start()
            while self.frame is None:
                time.sleep(0)

    def get_frame(self):
        Camera.last_access = time.time()
        self.initialize()
        return self.frame

    @classmethod
    def _thread(cls):
        with picamera.PiCamera() as camera:
            camera.resolution = (640, 480)
            camera.hflip = True
            camera.vflip = True
            camera.start_preview()
            time.sleep(2)
            stream = io.BytesIO()
            for foo in camera.capture_continuous(stream, 'jpeg',
                                                 use_video_port=True):
                stream.seek(0)
                cls.frame = stream.read()
                stream.seek(0)
                stream.truncate()
                if time.time() - cls.last_access > 10:
                    break
        cls.thread = None

if __name__ == '__main__':
    app.run(host='192.168.1.100', port=8000, debug=True, threaded=True, ssl_context='adhoc')