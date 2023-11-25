#!/usr/bin/python3

import os
import sys
import errno

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
    cluster = 1024
    t_dir = 0
    t_unidad = 0

    def __init__(self, f: str):
        self.imagen = open(f, 'rb+')

        # Firma
        tmp = imagen.read(8)
        if not tmp == b"FiUnamFS":
            raise NotFiUnamPartitionExc()

        # Version
        imagen.seek(10)
        tmp = imagen.read(4)
        if not tmp == b"24.1":
            raise UnsupportedVersionExc()

        # Etiqueta
        imagen.seek(20)
        self.etiqueta = imagen.read(19)

        # Cluster
        imagen.seek(40)
        self.cluster = btoi(imagen.read(4))

        # Tamano de directorio
        imagen.seek(45)
        self.t_dir = btoi(imagen.read(4))

        # Tamano de unidad
        imagen.seek(50)
        self.t_unidad = btoi(imagen.read(42)
