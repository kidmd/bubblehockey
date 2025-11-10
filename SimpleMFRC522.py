# A simple class to handle the MFRC522 RFID reader/writer.
#
# Copyright (c) 2021 Daniel Perron
#
# This file is part of MFRC522-python.
#
# MFRC522-python is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# MFRC522-python is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with MFRC522-python.  If not, see <https://www.gnu.org/licenses/>.

from MFRC522 import MFRC522


class SimpleMFRC522:

  KEY = [0xFF,0xFF,0xFF,0xFF,0xFF,0xFF]
  BLOCK_ADDRS = [8, 9, 10]

  def __init__(self, bus=0, device=0, spd=1000000):
    self.reader = MFRC522(bus,device,spd)

  def read(self):
      id, text = self.read_no_block()
      while not id:
          id, text = self.read_no_block()
      return id, text

  def read_id(self):
    id = self.read_id_no_block()
    while not id:
      id = self.read_id_no_block()
    return id

  def read_id_no_block(self):
      (status, TagType) = self.reader.MFRC522_Request(self.reader.PICC_REQIDL)
      if status != self.reader.MI_OK:
          return None
      (status, uid) = self.reader.MFRC522_Anticoll(self.reader.PICC_ANTICOLL1)
      if status != self.reader.MI_OK:
          return None
      return self.uid_to_num(uid)

  def read_no_block(self):
    (status, TagType) = self.reader.MFRC522_Request(self.reader.PICC_REQIDL)
    if status != self.reader.MI_OK:
        return None, None
    (status, uid) = self.reader.MFRC522_Anticoll(self.reader.PICC_ANTICOLL1)
    if status != self.reader.MI_OK:
        return None, None
    id = self.uid_to_num(uid)
    self.reader.MFRC522_SelectTag(uid)
    status = self.reader.MFRC522_Auth(self.reader.PICC_AUTHENT1A, 11, self.KEY, uid)
    data = []
    text_read = ''
    if status == self.reader.MI_OK:
        for block_num in self.BLOCK_ADDRS:
            block = self.reader.MFRC522_Read(block_num)
            if block:
                data += block
        if data:
            try:
                text_read = ''.join(map(chr, data))
            except:
                pass
    self.reader.MFRC522_StopCrypto1()
    return id, text_read

  def write(self, text):
      id, text_in = self.write_no_block(text)
      while not id:
          id, text_in = self.write_no_block(text)
      return id, text_in

  def write_no_block(self, text):
      (status, TagType) = self.reader.MFRC522_Request(self.reader.PICC_REQIDL)
      if status != self.reader.MI_OK:
          return None, None
      (status, uid) = self.reader.MFRC522_Anticoll(self.reader.PICC_ANTICOLL1)
      if status != self.reader.MI_OK:
          return None, None
      id = self.uid_to_num(uid)
      self.reader.MFRC522_SelectTag(uid)
      status = self.reader.MFRC522_Auth(self.reader.PICC_AUTHENT1A, 11, self.KEY, uid)
      self.reader.MFRC522_Read(11)
      if status == self.reader.MI_OK:
          data = bytearray()
          data.extend(bytearray(text.ljust(len(self.BLOCK_ADDRS) * 16).encode('ascii')))
          i = 0
          for block_num in self.BLOCK_ADDRS:
              self.reader.MFRC522_Write(block_num, data[(i*16):(i+1)*16])
              i += 1
      self.reader.MFRC522_StopCrypto1()
      return id, text[0:(len(self.BLOCK_ADDRS) * 16)]

  def uid_to_num(self, uid):
      n = 0
      for i in range(0, 5):
          n = n * 256 + uid[i]
      return n

