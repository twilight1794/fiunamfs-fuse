#!/usr/bin/python3

import logging
import os
import sys
import errno
import time
from datetime import datetime
from fusepy import FUSE, FuseOSError, Operations, LoggingMixIn

def btoi(b):
    """
    Convierte un array de 32 bits little-endian a un tipo int
    """
    return b[0]+(b[1]*256)+(b[2]*(256**2))+(b[3]*(256**3))

def itob(i):
    """
    Convierte un tipo int a un array de 32 bits little-endian
    """
    ba = bytearray()
    op = i
    p3 = op//(256**3)
    op -= p3*(256**3)
    p2 = op//(256**2)
    op -= p2*(256**2)
    p1 = op//256
    op -= p1*256
    ba.extend((op, p1, p2, p3))
    return ba

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

class NameTooLargeExc(Exception):
    """
    El nombre de archivo propuesto tiene más de 14 caracteres
    """

class FiUnamArchivo:
    def __init__(self, b):
        if type(b) == bytes:
            self.nombre = b[1:15].decode(encoding="us-ascii").strip()
            self.tamano = btoi(b[16:19]+bytes(1)) # NOTE: 4 o 3 bytes
            self.cluster_ini = btoi(b[20:23]+bytes(1)) # Idem
            self.fecha_creacion = datetime.strptime(b[24:38].decode(), "%Y%m%d%H%M%S")
            self.fecha_modificacion = datetime.strptime(b[38:52].decode(), "%Y%m%d%H%M%S")
        elif type(b) == tuple:
            self.nombre = b[0]
            self.tamano = 0
            self.cluster_ini = b[1]
            self.fecha_creacion = datetime.now()
            self.fecha_modificacion = datetime.now()

    def tobytes(self):
        ba = bytearray()
        ba.append(45)
        ba.extend(self.nombre.ljust(14).encode("us-ascii"))
        ba.extend(itob(self.tamano)[:3])
        ba.append(0)
        ba.extend(itob(self.cluster_ini)[:3])
        ba.append(0)
        ba.extend(self.fecha_creacion.strftime("%Y%m%d%H%M%S").encode("us-ascii"))
        ba.extend(self.fecha_modificacion.strftime("%Y%m%d%H%M%S").encode("us-ascii"))
        return bytes(ba)

class FiUnamFS(LoggingMixIn, Operations):
    etiqueta = ""
    cluster = 1024
    t_dir = 0
    t_unidad = 0
    entradas = {}
    entradas_vacias = set()
    descriptores = []

    def _existe(self, f: str):
        if f.startswith("/"):
            n = f[:1]
        else:
            n = f
        for k, v in self.entradas.items():
            if v.nombre == n:
                return k
        return None

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

    # Sistema de archivos
    def access(self, path, mode):
        return self._existe(path) and not(mode & 1 == 1)

    def chmod(self, path, mode):
        raise NotImplementedError()

    def chown(self, path, uid, gid):
        raise NotImplementedError()

#    def getattr(self, path, fh=None):
#        inodo = self._existe(path)
#        if not inodo:
#            raise FuseOSError(errno.ENOENT)
#        return dict(
#            st_atime=time.mktime(self.entradas[self._existe(path)].fecha_modificacion.timetuple()),
#            st_ctime=time.mktime(self.entradas[self._existe(path)].fecha_creacion.timetuple()),
#            st_gid=os.getgid(),
#            st_ino=self._existe(path),
#            st_mode=0o100666,
#            st_mtime=time.mktime(self.entradas[self._existe(path)].fecha_modificacion.timetuple()),
#            st_nlink=1,
#            st_size=0,#self.entradas[self._existe(path)].tamano,
#            st_uid=os.getuid()
#        )

    def readdir(self, path, fh):
        lista = [ ".", ".." ]
        for e in self.entradas.values():
            print("readdir", e.nombre)
            lista.append(e.nombre)
        return lista

    def readlink(self, path):
        raise NotImplementedError()

    def mknod(self, path, mode, dev):
        raise NotImplementedError()

    def rmdir(self, path):
        raise NotImplementedError()

    def mkdir(self, path, mode):
        raise NotImplementedError()

    def statfs(self, path):
        return dict(f_bsize=self.cluster, f_blocks=self.t_unidad, f_bavail=len(self.entradas_vacias))

    def unlink(self, path):
        inodo = self._existe(path)
        del self.entradas[inodo]
        self.entradas_vacias.add(inodo)
        # Escribir en la imagen

    def symlink(self, name, target):
        raise NotImplementedError()

    def rename(self, old, new):
        inodo = self._existe(new)
        if inodo:
            raise OSError(new)
        elif len(new)>14:
            raise NameTooLargeExc()
        else:
            self.entradas[inodo].nombre = new
            # Escribir en la imagen

    def link(self, target, name):
        raise NotImplementedError()

    def utimens(self, path, times=None):
        # Pero es solo implementar la actualización de hora...
        raise NotImplementedError()

    # Archivos
    def open(self, path, flags):
        inodo = self._existe(path)
        try:
            return self.descriptores.index(inodo)
        except ValueError:
            self.descriptores.append(inodo)
            return len(self.descriptores) - 1

    def create(self, path, mode, fi=None):
        if len(self.entradas_vacias):
            inodo_n = min(list(self.entradas_vacias))
            self.entradas_vacias.remove(inodo_n)
            self.entradas[inodo_n] = FiUnamArchivo((path[:1], inodo_n))
            self.imagen.seek(self.cluster+64*inodo_n)
            self.imagen.write(self.entradas[inodo_n].tobytes())
        else:
            raise OSError()

    def read(self, path, length, offset, fh):
        inodo = self._existe(path)
        print(inodo, 1)
        self.imagen.seek(self.entradas[inodo].cluster_ini * self.cluster + (offset or 0))
        print(inodo, 2)
        return self.imagen.read(length or self.entradas[inodo].tamano)

    def write(self, path, buf, offset, fh):
        inodo = self._existe(path)
        self.imagen.seek(self.entradas[inodo].cluster_ini * self.cluster + (offset or 0))
        self.imagen.write(buf)
        self.entradas[inodo].tamano =+ len(buf) + (offset or 0)
        return len(buf)

    def truncate(self, path, length, fh=None):
        inodo = self._existe(path)
        if length >= self.entradas[inodo].tamano:
            dif = length - self.entradas[inodo].tamano
            self.imagen.seek(self.entradas[inodo].cluster_ini * self.cluster + self.entradas[inodo].tamano)
            self.imagen.write(bytes(dif))
        else:
            dif = self.entradas[inodo].tamano - length
            self.imagen.seek(self.entradas[inodo].cluster_ini * self.cluster + length)
        self.imagen.write(bytes(dif))
        self.entradas[inodo].tamano = length

    def flush(self, path, fh):
        pass # No implementado, los cambios se realizan inmmediatamente

    def release(self, path, fh):
        inodo = self._existe(path)
        self.descriptores.remove(inodo)

    def fsync(self, path, fdatasync, fh):
        pass # No implementado, los cambios se realizan inmmediatamente

logging.basicConfig(level=logging.DEBUG)
FUSE(FiUnamFS(sys.argv[1]), sys.argv[2], nothreads=True, foreground=True, allow_other=True)
