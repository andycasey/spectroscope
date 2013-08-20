# coding: utf-8

""" Handles the loading and interpolation of flux models for SCOPE. """

from __future__ import division, print_function

__author__ = "Andy Casey <acasey@mso.anu.edu.au>"

# Standard library
import logging
import os
import re

from glob import glob

# Third-party
import numpy as np
import pyfits

__all__ = ['Models', 'load_model_data']

class Models(object):
    """Class for interpolating model fluxes for SCOPE."""

    def __init__(self, configuration):
        self.configuration = configuration

        # Dispersions
        self.dispersion = {}
        for beam, dispersion_filename in configuration['models']['dispersion_filenames'].iteritems():
            self.dispersion[beam] = load_model_data(dispersion_filename)

        grid_points = {}
        flux_filenames = {}

        # Read the points from filenames
        for beam in configuration['models']['flux_filenames']:
            folder = configuration['models']['flux_filenames'][beam]['folder']
            re_match = configuration['models']['flux_filenames'][beam]['re_match']

            all_filenames = glob(os.path.join(folder, '*'))

            points = []
            matched_filenames = []
            for filename in all_filenames:
                match = re.match(re_match, os.path.basename(filename))

                if match is not None:
                    if not hasattr(self, 'point_dtypes'):
                        point_dtypes = []
                        groups = match.groups()

                        groupdict = match.groupdict()
                        for value in match.groupdict().itervalues():
                            if groups.count(value) > 1: break
                            point_dtypes.append(match.groupdict().keys()[groups.index(value)])

                        if len(point_dtypes) == len(groups):
                            self.point_dtypes = point_dtypes

                    points.append(map(float, match.groups()))
                    matched_filenames.append(filename)

            grid_points[beam] = points
            flux_filenames[beam] = matched_filenames

        # If it's just the one beam, it's easy!
        first_beam = configuration['models']['flux_filenames'].keys()[0]
        self.grid_points = np.array(grid_points[first_beam])
        
        if len(configuration['models']['flux_filenames'].keys()) == 1:
            self.flux_filenames = flux_filenames[first_beam]

            return None

        else:
            self.flux_filenames = {first_beam: flux_filenames[first_beam]}

        # Put all points and filenames on the one scale
        for beam in configuration['models']['flux_filenames'].keys()[1:]:
            
            points = grid_points[beam]
            if len(points) != len(self.grid_points):
                raise ValueError("number of model points found in {first_beam} beam ({num_first_beam})"
                    " did not match the number in {this_beam} beam ({num_this_beam})"
                    .format(first_beam=first_beam, num_first_beam=len(self.grid_points), this_beam=beam,
                        num_this_beam=len(points)))

            sort_indices = []

            for point in points:
                index = self.check_grid_point(point)
                sort_indices.append(index)

            self.flux_filenames[beam] = [flux_filenames[beam][index] for index in sort_indices]

        return None


    def get_nearest_neighbours(self, point, n=1):
        """Returns the indices for the nearest `n` neighbours to the given `point` in each dimension.

        Inputs
        ------
        point : list of `float` values
            The point to find neighbours for.

        n : int
            The number of neighbours to find either side of `point` in each dimension.
            Therefore the total number of points returned will be dim(point)^n.
        """

        if len(point) != self.grid_points.shape[1]:
            raise ValueError("point length ({length}) is incompatible with grid shape ({shape})"
                .format(length=len(point), shape=self.grid_points.shape))

        try: n = int(n)
        except TypeError:
            raise TypeError("number of neighbours must be an integer-type")
        if 1 > n:
            raise ValueError("number of neighbours must be a positive integer-type")

        indices = set(np.arange(len(self.grid_points)))
        for i, point_value in enumerate(point):
            difference = np.unique(self.grid_points[:, i] - point_value)

            limit_min = difference[np.where(difference < 0)][-n:][0] + point_value
            limit_max = difference[np.where(difference > 0)][:n][-1] + point_value
    
            these_indices = np.where((limit_max >= self.grid_points[:, i]) & (self.grid_points[:, i] >= limit_min))[0]
            indices.intersection_update(these_indices)

        return np.array(list(indices))


    def check_grid_point(self, point):
        """Checks whether the point provided exists in the grid of models. If so,
        its index is returned.

        Inputs
        ------
        point : list of float values
            The point of interest.
        """

        index = np.where(np.all(np.equal(self.grid_points - point, np.zeros(len(point))), 1))[0]

        if len(index) > 0:
            return index[0]

        return False


    def interpolate_flux(self, point, beams='all', kind='linear', **kwargs):
        """Interpolates through the grid of models to the given `point` and returns
        the interpolated flux.

        Inputs
        ------
        point : list of `float` values
            The point to interpolate to.

        beams : str, optional
            The beams to interpolate flux for. If this is 'all', a dictionary is
            returned with interpolated fluxes for all beams.

        kind : str or int, optional
            Specifies the kind of interpolation as a string
            ('linear', 'nearest', 'zero', 'slinear', 'quadratic', 'cubic')
            or as an integer specifying the order of the spline interpolator
            to use. Default is 'linear'.
        """

        neighbour_indices = self.get_nearest_neighbours(point)

        if beams is 'all':
            beams = self.flux_filenames.keys()

        elif not isinstance(beams, (list, tuple)):
            beams = [beams]

        for beam in beams:
            if beam not in self.flux_filenames.keys():
                raise ValueError("could not find '{beam}' beam".format(beam=beam))

        interpolated_flux = {}
        for beam in beams:

            beam_flux = np.zeros((
                len(neighbour_indices),
                len(self.dispersion[beam])
                ))
            beam_flux[:] = np.nan

            # Load the flux points
            for i, index in enumerate(neighbour_indices):
                beam_flux[i, :] = load_model_data(self.flux_filenames[beam][index])
            
            interpolated_flux[beam] = scipy.interpolate.griddata(
                self.grid_points[neighbour_indices],
                beam_flux,
                [point],
                **kwargs).flatten()

        return interpolated_flux




def load_model_data(filename, **kwargs):
    """Loads dispersion/flux values from a given filename. This can be either a 1-column ASCII
    file, or a single extension FITS file.

    Inputs
    ------
    filename : `str`
        The filename to load the values from.
    """

    if not os.path.exists(filename):
        raise IOError("filename '{filename}' does not exist".format(filename=filename))

    try:
        image = pyfits.open(filename, **kwargs)

    except:
        data = np.loadtxt(filename, **kwargs)

    else:
        data = image[0].data
        image.close()

    finally:
        return data



        