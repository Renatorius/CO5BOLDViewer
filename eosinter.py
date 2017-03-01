# -*- coding: utf-8 -*-
"""
Created on Mon Nov 16 19:27:59 2015

@author: René Georg Salhab
"""

from __future__ import division, print_function

import numexpr as ne
import numpy as np

try:
    import eosinterx as eosx
    eosx_available = True
except:
    eosx_available = False

import uio_eos as ue

print("eosx available (eosinter):", eosx_available)

class EosInter:
    def __init__(self, fname):
        """
            Description
            -----------
                Opens an .eos-file given by :param fname.
            Input
            -----
                :param fname: string, path and name of file with eos-related tables.
        """

        eosfile = ue.File(fname)

        self.eosf = eosfile

        self.cent = eosfile.block[0]['c1'].data.T
        self.cent = self.cent.newbyteorder()
        self.cent = self.cent.byteswap()

        self.cpress = eosfile.block[0]['c2'].data.T
        self.cpress = self.cpress.newbyteorder()
        self.cpress = self.cpress.byteswap()

        self.ctemp = eosfile.block[0]['c3'].data.T
        self.ctemp = self.ctemp.newbyteorder()
        self.ctemp = self.ctemp.byteswap()

        self.lnx11d = np.log(eosfile.block[0]['x1'].data + eosfile.block[0]['x1shift'].data).squeeze()
        self.lnx21d = np.log(eosfile.block[0]['x2'].data + eosfile.block[0]['x2shift'].data).squeeze()
        self.x2shift = eosfile.block[0]['x2shift'].data

        n1 = self.lnx11d.size - 1
        n2 = self.lnx21d.size - 1

        self.x1fac = n1 / (self.lnx11d.max() - self.lnx11d.min())
        self.x2fac = n2 / (self.lnx21d.max() - self.lnx21d.min())

    def __prep(self, rho, ei):
        nx1 = rho.size - 1
        nx2 = rho.size - 2

        lnx1 = ne.evaluate("log(rho)")
        lnx2 = ne.evaluate("log(ei+x2)", local_dict={'ei': ei}, global_dict={'x2': self.x2shift})

        i1 = ne.evaluate("(lnx1 - x1off) * x1fac", local_dict={'lnx1': lnx1}, global_dict={'x1fac': self.x1fac,
                                                               'x1off': self.lnx11d[0]}).astype(np.int32).clip(0, nx1)
        i2 = ne.evaluate("(lnx2 - x2off) * x2fac", local_dict={'lnx2': lnx2}, global_dict={'x2fac': self.x2fac,
                                                               'x2off': self.lnx21d[0]}).astype(np.int32).clip(0, nx2)

        lnx11d = self.lnx11d[i1]
        lnx21d = self.lnx21d[i2]

        x1ta = ne.evaluate('lnx1 - lnx11d')
        x2ta = ne.evaluate('lnx2 - lnx21d')

        return x1ta, x2ta, i1, i2

    def unit(self, quantity="Pressure"):
        """
            Description
            -----------
                returns the unit of :param quantity
            Input
            -----
                :param quantity: string, the demanded quantity.
                    Possibilities: Entropy: "Entropy", "entropy", "E", "e"
                                   Pressure: "Pressure", "pressure", "P", "p"
                                   Temperature: "Temperature", "temperature", "T", "t"
            Output
            ------
                :return: string, unit of :param quantity:.
        """
        if quantity in ["Entropy", "entropy", "E", "e"]:
            unit = self.eosf.block[0]['c1'].params['u']
        elif quantity in ["Pressure", "pressure", "P", "p"]:
            unit = self.eosf.block[0]['c2'].params['u']
        elif quantity in ["Temperature", "temperature", "T", "t"]:
            unit = self.eosf.block[0]['c3'].params['u']
        else:
            raise ValueError('{0} is not valid quantity'.format(quantity))
        return unit


    def STP(self, rho, ei, quantity="Pressure"):
        """
            Description
            -----------
                Computes the entropy, gas-pressure, or temperature.
            Input
            -----
                :param rho: ndarray, shape of simulation box, density-field
                :param ei: ndarray, shape of simulation box, internal energy-field
                :param quantity: string, the demanded quantity.
                    Possibilities: Entropy: "Entropy", "entropy", "E", "e"
                                   Pressure: "Pressure", "pressure", "P", "p"
                                   Temperature: "Temperature", "temperature", "T", "t"
            Output
            ------
                :return: ndarray, shape of simulation box, values of :param quantity:.
        """
        if not eosx_available:
            raise IOError("Compilation of eosinterx.pyx necessary.")
        x1ta, x2ta, i1, i2 = self.__prep(rho, ei)

        funcs = {3: eosx.STP3D, 4: eosx.STP4D}
        try:
            func = funcs[rho.ndim]
        except KeyError:
            raise ValueError("Wrong dimension. Only 3D- and 4D-arrays supported.")

        if quantity in ["Entropy", "entropy", "E", "e"]:
            C = self.cent
        elif quantity in ["Pressure", "pressure", "P", "p"]:
            C = self.cpress
        elif quantity in ["Temperature", "temperature", "T", "t"]:
            C = self.ctemp
        else:
            raise ValueError("{0} as quantity is not supported.".format(quantity))

        if quantity in ["Entropy", "entropy", "E", "e"]:
            return func(rho, ei, C, i1, i2, x1ta, x2ta)
        else:
            return ne.evaluate("exp(val)", local_dict={'val': func(rho, ei, C, i1, i2, x1ta, x2ta)})

    def PandT(self, rho, ei):
        """
            Description
            -----------
                Computes gas-pressure and temperature.
            Input
            -----
                :param rho: ndarray, shape of simulation box, density-field
                :param ei: ndarray, shape of simulation box, internal energy-field
            Output
            ------
                :return: ndarray, shape of simulation box, pressure,
                         ndarray, shape of simulation box, temperature.
        """
        if not eosx_available:
            raise IOError("Compilation of eosinterx.pyx necessary.")
        x1ta, x2ta, i1, i2 = self.__prep(rho, ei)

        if rho.ndim == 3:
            return eosx.PandT3D(rho, ei, self.cpress, self.ctemp, i1, i2, x1ta, x2ta)
        elif rho.ndim == 4:
            return eosx.PandT4D(rho, ei, self.cpress, self.ctemp, i1, i2, x1ta, x2ta)
        else:
            raise ValueError("Wrong dimension. Only 3D- and 4D-arrays supported.")

    def Pall(self, rho, ei):
        """
            Description
            -----------
                Computes gas-pressure and its derivatives dPdrho and dPdei.
            Input
            -----
                :param rho: ndarray, shape of simulation box, density-field
                :param ei: ndarray, shape of simulation box, internal energy-field
            Output
            ------
                :return: ndarray, shape of simulation box, pressure,
                         ndarray, shape of simulation box, dPdrho.
                         ndarray, shape of simulation box, dPdei.
        """
        if not eosx_available:
            raise IOError("Compilation of eosinterx.pyx necessary.")
        x1ta, x2ta, i1, i2 = self.__prep(rho, ei)

        if rho.ndim == 3:
            return eosx.Pall3D(rho, ei, self.cpress, i1, i2, x1ta, x2ta, self.x2shift)
        elif rho.ndim == 4:
            return eosx.Pall4D(rho, ei, self.cpress, i1, i2, x1ta, x2ta, self.x2shift)
        else:
            raise ValueError("Wrong dimension. Only 3D- and 4D-arrays supported.")

    def Tall(self, rho, ei):
        """
            Description
            -----------
                Computes temperature and its derivative dTdei.
            Input
            -----
                :param rho: ndarray, shape of simulation box, density-field
                :param ei: ndarray, shape of simulation box, internal energy-field
            Output
            ------
                :return: ndarray, shape of simulation box, pressure,
                         ndarray, shape of simulation box, dTdei.
        """
        if not eosx_available:
            raise IOError("Compilation of eosinterx.pyx necessary.")
        x1ta, x2ta, i1, i2 = self.__prep(rho, ei)

        if rho.ndim == 3:
            return eosx.Tall3D(rho, ei, self.ctemp, i1, i2, x1ta, x2ta, self.x2shift)
        elif rho.ndim == 4:
            return eosx.Tall4D(rho, ei, self.ctemp, i1, i2, x1ta, x2ta, self.x2shift)
        else:
            raise ValueError("Wrong dimension. Only 3D- and 4D-arrays supported.")
