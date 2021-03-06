import os
from queue import Queue
from threading import Thread
import threading
from http.status import *
import time
from cache.cache import *
from http.http_response import HTTPResponse
from selector import sel
from utils.event_loop_app_exception import EventLoopAppException
import socket

NUM_OF_THREADS = 1

class EventLoop:

	def __init__(self, event_queue, cache_policy=LRU):
		self.event_queue = event_queue
		self.disk_io_queue = Queue()
		self.cache = Cache.build(cache_policy)

		for i in range(NUM_OF_THREADS):
			t = Thread(target=self.read)
			t.start()

	def start(self):
		while True:
			try:
				self.execute()
			except EventLoopAppException:
				pass

	def execute(self):
		event = self.event_queue.dequeue()
		if event.is_disk_io():
			# Check whether the requested data is cached.
			cached_response_bytes = self.cache.get(event.request_uri)
			if cached_response_bytes != -1:
				event.response_bytes = cached_response_bytes
				event.disk_io = False
				self.send_event(event)
				EventLoop.close_or_keep_alive(event)
			else:
				self.disk_io_queue.put(event)
		else:
			self.send_event(event)
			EventLoop.close_or_keep_alive(event)

	@staticmethod
	def close_or_keep_alive(event):
#		print("Event_connection_info:" + str(event.connection))
		if event.connection == 'keep-alive':
#			print("Event Connnection is keep alive!")
			pass
		else:
			sel.unregister(event.CLIENT_SOCKET)
			event.CLIENT_SOCKET.close()
#			print("Connection from client is closed.")

	def send_event(self, event):
#		print("Event sending started!")
#		begin = time.time()
		bytes_to_send = HTTPResponse.respond(HTTP_200_OK, event)
		event.CLIENT_SOCKET.setblocking(True)
		event.CLIENT_SOCKET.sendall(bytes_to_send)
#		end = time.time()
#		print('Send elapsed time: ' + str(end - begin))
#		print("Event Sent!")

	def read(self):
		while True:
			self.read_aux()

	def read_aux(self):
		event = self.disk_io_queue.get(block=True, timeout=None)
		event = self.process_disk_io(event)
#		self.disk_io_queue.task_done()
		self.send_event(event)
#		self.event_queue.enqueue(event)

	def process_disk_io(self, event):
#		begin = time.time()
		try:
			with open(os.path.dirname(__file__) + '/resources' + event.request_uri, 'rb') as f:
				event.response_bytes = f.read()
				# Newly read file is inserted into cache.
				self.cache.set(event.request_uri, event.response_bytes)
		except: 
			raise EventLoopAppException(HTTP_404_NOT_FOUND, 'File does not exist. Cannot process event', event)
#		end = time.time()
#		print('Disk I/O elapsed time: ' + str(end-begin))
		event.disk_io = False
		return event

