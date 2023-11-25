#!/usr/bin/python3

import os
import sys
#import errno
from datetime import datetime
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
    La imagen no contiene la firma, no es una partición FiUnamFS
    """
    c = 1

class UnsupportedVersionExc(Exception):
    """
    La versión de FiUnamFS usada no está soportada
    """
    c = 2

class TruncatedImageExc(Exception):
    """
    La imagen no tiene el tamaño mínimo para ser una imagen válida
    """
    c = 3

class FiUnamArchivo:
    def __init__(self, b):
        self.nombre = b[1:15].decode(encoding="us-ascii").strip()
        self.tamano = btoi(b[16:20]) # NOTE: 4 o 3 bytes
        self.cluster_ini = btoi(b[20:24]) # Idem
        self.fecha_creacion = datetime.strptime(b[24:38].decode(), "%Y%m%d%H%M%S")
        self.fecha_modificacion = datetime.strptime(b[38:52].decode(), "%Y%m%d%H%M%S")

class FiUnamFS(Operations):
    etiqueta = ""
    cluster = 1024
    t_dir = 0
    t_unidad = 0
    entradas = {}
    entradas_vacias = set()

    def __init__(self, f: str):
        if os.path.getsize(f) < 54:
            raise TruncatedImageExc()

        self.imagen = open(f, 'rb+')

        # Firma
        if not self.imagen.read(8) == b"FiUnamFS":
            raise NotFiUnamPartitionExc()

        # Version
        self.imagen.seek(10)
        if not self.imagen.read(4) == b"24.1":
            raise UnsupportedVersionExc()

        # Etiqueta
        self.imagen.seek(20)
        self.etiqueta = self.imagen.read(19)

        # Tamaño de cluster
        self.imagen.seek(40)
        self.cluster = btoi(self.imagen.read(4))

        # Tamaño de directorio
        self.imagen.seek(45)
        self.t_dir = btoi(self.imagen.read(4))

        # Tamaño de unidad
        self.imagen.seek(50)
        self.t_unidad = btoi(self.imagen.read(4))

        # Directorio
        self.imagen.seek(self.cluster)
        for i in range(self.cluster*self.t_dir//64):
            raw_entrada = self.imagen.read(64)

            # Tipo de nodo
            if raw_entrada[0] == 45: # Es un archivo
                self.entradas[i] = FiUnamArchivo(raw_entrada)
            elif raw_entrada[0] == 47: # Es una entrada vacía
                self.entradas_vacias.add(i)
