#!/usr/bin/python3

import os
import sys
import errno
import struct

from fusepy import FUSE, FuseOSError, Operations, fuse_get_context

def btoi(b):
    """
    Convierte un array de 32 bits little-endian a un tipo int
    """
    return b[0]+(b[1]*256)+(b[2]*(256**2))+(b[3]*(256**3))

def itob(i):
    """
    Convierte un tipo int a un array de 32 bits little-endian
    """
    op = i
    p3 = op//(256**3)
    op -= p3*(256**3)
    p2 = op//(256**2)
    op -= p2*(256**2)
    p1 = op//256
    op -= p1*256
    return chr(op) + chr(p1) + chr(p2) + chr(p3)

class NotFiUnamPartitionExc(Exception):
    """
    La partición no contiene la firma, no es una partición FiUnamFS
    """
    c = 1

class UnsupportedVersionExc(Exception):
    """
    La versión de FiUnamFS usada no está soportada
    """
    c = 2

class FiUnamFS(Operations):
    etiqueta = ""
    
    bl = open('fiunamfs.img', 'r+')
    sb = bl.read(1024)
    if not sb[:8] == b"FiUnamFS":
        raise NotFiUnamPartitionExc()
    if not sb[10:14] == b"24.1":
        raise UnsupportedVersionExc()
    etiqueta = sb[20:39]
