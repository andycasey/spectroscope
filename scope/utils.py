# coding: utf-8

""" General utilities for SCOPE. """

from __future__ import division, print_function

__author__ = "Andy Casey <acasey@mso.anu.edu.au>"

# Standard library
import logging
import os

# Third-party
import numpy as np

__all__ = ['find_spectral_overlap']

def find_spectral_overlap(dispersion_maps, interval_resolution=1):
    """Checks whether the dispersion maps overlap or not.

    Inputs
    ------
    dispersion_maps : list of list-types of length 2+
        The dispersion maps in the format [(wl_1, wl_2, ... wl_N), ..., (wl_start, wl_end)]
    
    interval_resolution : float, Angstroms
        The resolution at which to search for overlap. Any overlap less than the
        `interval_resolution` may not be detected.

    Returns
    -------
    None if no overlap is found, otherwise the wavelength near the overlap is returned.
    """

    all_min = map(np.min, dispersion_maps)
    all_max = map(np.max, dispersion_maps)

    interval_tree_disp = np.arange(all_min, all_max + interval_tree_resolution, interval_tree_resolution)
    interval_tree_flux = np.zeros(len(interval_tree_disp))

    for dispersion_map in dispersion_maps:

        wlstart, wlend = np.min(dispersion_map), np.max(dispersion_map)
        idx = np.searchsorted(interval_tree_disp, [wlstart, wlend + interval_tree_resolution])

        interval_tree_flux[idx[0]:idx[1]] += 1

    # Any overlap?
    if np.max(interval_tree_flux) > 1:
        idx = np.where(interval_tree_flux > 1)[0]
        wavelength = interval_tree_disp[idx[0]]
        return wavelength
    
    else:
        return None


