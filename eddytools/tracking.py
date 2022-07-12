'''tracking

Collection of functions needed for the tracking of mesoscale eddies
detected with the module `detection.py` of this packkage.

'''

import sys
import os
import numpy as np
from scipy import interpolate
import operator
import pandas as pd
import xarray as xr
import pickle
import cftime as cft


def load_rossrad(input_path):
    ''' Load first baroclinic wave speed [m/s] and Rossby radius
    of deformation [km] data from rossrad.dat (Chelton et al., 1998)

    Also calculated is the first baroclinic Rossby wave speed [m/s]
    according to the formula:  cR = -beta rossby_rad**2

    Parameters
    ----------
    input_path : str
        Path to the file `rossrad.dat`

    Returns
    ------
    rossrad : dict
        Dictionary containing the 2D (lat, lon) first baroclinic Rossby
        radius 'rossby_rad', the first baroclinic wave speed 'c1' and
        the first baroclinic Rossby wave speed 'cR'.
    '''
    # load rossby radius and first baroclinic wave speed c1 from file
    data = pd.read_table(input_path + 'rossrad.dat', sep=r'\s{1,}',
                         engine='python', header=None)
    data.columns = ['lat', 'lon', 'c1', 'rossby_rad']

    # write data from file to output dict
    # calculate first baroclinic rossby wave speed
    R = 6371.e3  # Radius of Earth [m]
    Sigma = 2 * np.pi / (24 * 60 * 60)  # Rotation frequency of Earth [rad/s]
    beta = (2 * Sigma / R) * np.cos(data['lat'] * np.pi / 180)  # 1 / m s
    data['cR'] = (-1) * beta * (1e3 * data['rossby_rad']) ** 2
    return data


def is_leap_year(year):
    """Determine whether a year is a leap year."""
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def calculate_d(dE, lon, lat, rossrad, dt):
    ''' Calculates length of search area to the west of central point.
    This is equal to the length of the search area to the east of
    central point (dE)  except for the tropics ( abs(lat) < 18 deg ),
    where the distance a Rossby wave travels in one time step
    (dt) is used instead.

    Parameters
    ----------
    dE : float or int
        Extend of the search area to the east (in km) from the eddy center at
        prevoius timestep.
    lon : array
        Longitude vector of the grid on which eddies were detected.
    lat : array
        Latitude vector of the grid on which eddies were detected.
    rossrad : dict
        Dictionary from load_rossrad() output.
    dt : int
        Timestep in days of the grid on which eddies were detected.

    Returns
    -------
    d : float or inr
        Extent of the search ellipsis to the west.
    '''
    if np.abs(lat) < 18:
        if lon < 0.:
            lon_pos = lon + 360.
        else:
            lon_pos = lon
        # Rossby wave speed [km/day]
        c = interpolate.griddata(np.array([rossrad['lon'], rossrad['lat']]).T,
                                 rossrad['cR'],
                                 (lon_pos, lat),
                                 method='linear') * 86400. / 1000.
        d = np.abs(1.75 * c * dt)
    else:
        d = dE

    return d


def is_in_ellipse(x0, y0, dE, d, x, y):
    '''Check if point (x,y) is contained in ellipse given by the equation

      (x-x1)**2     (y-y1)**2
      ---------  +  ---------  =  1
         a**2          b**2

    where:

      a = 0.5 * (dE + dW)
      b = dE
      x1 = x0 + 0.5 * (dE - dW)
      y1 = y0

    Parameters
    ----------
    x0 : float
        Eddy center lon at timestep t-1.
    y0 : float
        Eddy center lat at timestep t-1.
    dE : float
        Eastern extend of ellipsis.
    d : float
        Western extend of ellipsis.
    x : array
        Longitude vector of eddy centers at timestep t
    y : array
        Latitude vector of eddy centers at timestep t

    Returns
    -------
    elli : boolean array
        Boolean vector of length len(x)=len(y). True when (x,y) is
        inside the ellipsis
    '''
    # minimum western extend is dE
    dW = max([d, dE])

    b = dE  # minor axis
    a = 0.5 * (dE + dW)  # major axis

    x1 = x0 + 0.5*(dE - dW)  # center of ellipsis (shifted when dE != dW)
    y1 = y0

    elli = (x-x1)**2 / a**2 + (y-y1)**2 / b**2 <= 1
    return elli


def len_deg_lon(lat):
    '''Returns the length of one degree of longitude (at latitude
    specified) in km.

    Parameters
    ----------
    lat : array or float
        Latitude (can be a single values or an array).

    Returns
    -------
    lenlon : array or float
        Length of 1deg longitude at given latitude `lat`.
    '''

    R = 6371.  # Radius of Earth [km]

    lenlon = (np.pi / 180.) * R * np.cos(lat * np.pi/180.)
    return lenlon


def prepare(trac_param):
    ''' Preparation function for the eddy tracking.

    Loads the Rossby radius data, specifies the extent of the search region,
    and extracts the specified time range from the detected eddies.

    Parameters
    ----------
    trac_param : dict
        Dictionary with all the parameters needed for the eddy-tracking.
        The parameters are:
        trac_param = {
            'model': 'model_name', # either ORCA or MITgcm
            'grid': 'latlon', # either latlon or cartesian
            'start_time': 'YYYY-MM-DD', # time range start
            'end_time': 'YYYY-MM-DD', # time range end
            'calendar': 'standard', # calendar, must be either 360_day or
                                    # standard
            'dt': 5, # time step of the original fields
            'lon1': -180, # minimum longitude of detection region, either in
                          # the range (-180, 180) degrees or in m for a
                          # cartesian grid
            'lon2': -130, # maximum longitude of detection region, either
                          # (-180, 180) degrees or m
            'lat1': -55, # minimum latitude of detection region, either
                          # (-90, 90) degrees or m
            'lat2': -30, # maximum latitude of detection region, either
                          # (-90, 90) degrees or m
            'dE': 0., # maximum distance of search ellipsis from eddy center
                      # towards the east (if set to 0, it will be calculated
                      # as (150. / (7. / dt)))
            'eddy_scale_min': 0.75, # minimum factor by which eddy amplitude
                                    # and area can change in one timestep
            'eddy_scale_max': 1.5, # maximum factor by which eddy amplitude
                                   # and area can change in one timestep
            'dict': 0, # dictionary containing detected eddies to be used when
                       # not stored in files (set to 0 otherwise)
            'data_path': datapath, # path to the detected eddies pickle files
            'file_root': 'test', # root name of the files, usually CONF-EXP etc.
            'file_spec': 'eddies_OW0.3', # part of the file name following the
                                         # datestring
            # the resulting file name that will be searched for is then
            # data_path+file_root+_+datestring+_+file_spec+.pickle
            # datestring will be defined inside the function
            'ross_path': datapath + '/' # path to rossrad.dat containing
                                        # Chelton et al. 1998 Rossby radii
            }

    Returns
    -------
    eddies_time : index
        Datetime index containing the time steps at which eddies should be
        tracked.
    rossrad : dict
        Dictionary containing the 2D (lat, lon) first baroclinic Rossby
        radius 'rossby_rad', the first baroclinic wave speed 'c1' and
        the first baroclinic Rossby wave speed 'cR'.
    t_p : dict
        Same as `trac_param`, but the eastern extent of the search
        region `dE` has been modified.
    '''
    # Load the contents of the file with the Rossby radius data if we are on
    # a latlon grid
    t_p = trac_param.copy()
    if t_p['grid'] == 'latlon':
        rossrad = load_rossrad(trac_param['ross_path'])
    else:
        rossrad = []

    # calculate eastern extend of search region
    if trac_param['dE'] == 0:
        t_p['dE'] = 150. / (7. / trac_param['dt'])  # [km]
    elif trac_param['dE'] > 0:
        t_p['dE'] = trac_param['dE']
    else:
        print('Eastern extend of search region not properly specified')
        sys.exit()

    # Create a list of dates. For each of these dates, a file with detected
    # eddies will be read, so that tracks can be calculated.
    # This is rather complex, as we have to account for leap years.
    #
    # First we determine the start year and the end year of the period to
    # consider and calculate how many years this period includes.
    if trac_param['model'] == 'ORCA':
        time_hours = '12'
    elif trac_param['model'] == 'MITgcm':
        time_hours = '00'
    start_year = trac_param['start_time'][0:4]
    end_year = trac_param['end_time'][0:4]
    years = (int(end_year) - int(start_year))
    # For a standard calendar the behavior in leap years needs to be
    # considered: For the ORCA simulations, in leap years, all dates of 5-
    # daily output stay the same as in non-leap years EXCEPT for the 27th
    # February, which becomes the 28th Febuary... so we consruct a no-leap
    # year and change the one date later if necessary!
    if trac_param['calendar'] == 'standard':
        calendar_to_use = 'noleap'
    elif trac_param['calendar'] == '360_day':
        calendar_to_use = '360_day'
    eddies_time_range = xr.cftime_range(
        start=trac_param['start_time'] + ' ' + time_hours,
        end=trac_param['end_time'] + ' ' + time_hours,
        calendar=calendar_to_use,
        freq=str(trac_param['dt']) + 'D')
    # Now we take care of the leap years.
    eddies_time = list(np.zeros(len(eddies_time_range)))
    for tt in np.arange(0, len(eddies_time_range)):
        if (is_leap_year(eddies_time_range[tt].year)
            # If the current year is a leap year, change Feb. 27 to Feb. 28.
            & (eddies_time_range[tt].month == 2)
            & (eddies_time_range[tt].day == 27)
            & (trac_param['model'] == 'ORCA')):
            eddies_time[tt] = (str(eddies_time_range[tt].year)
                               + '-02-28 00:00:00')
        else:
            eddies_time[tt] = str(eddies_time_range[tt])
    return eddies_time, rossrad, t_p


def eddy_is_near(track, trac_param, un_items, range_un_items, rossrad):
    '''Test whether an eddy is near the eddy in `track`.

    Parameters
    ----------
    track : dict
        Dictionary of an eddy track.
    trac_param : dict
        Dictionary with all the parameters needed for the eddy-tracking.
        The parameters are:
        trac_param = {
            'model': 'model_name', # either ORCA or MITgcm
            'grid': 'latlon', # either latlon or cartesian
            'start_time': 'YYYY-MM-DD', # time range start
            'end_time': 'YYYY-MM-DD', # time range end
            'calendar': 'standard', # calendar, must be either 360_day or
                                    # standard
            'dt': 5, # time step of the original fields
            'lon1': -180, # minimum longitude of detection region, either in
                          # the range (-180, 180) degrees or in m for a
                          # cartesian grid
            'lon2': -130, # maximum longitude of detection region, either
                          # (-180, 180) degrees or m
            'lat1': -55, # minimum latitude of detection region, either
                          # (-90, 90) degrees or m
            'lat2': -30, # maximum latitude of detection region, either
                          # (-90, 90) degrees or m
            'dE': 0., # maximum distance of search ellipsis from eddy center
                      # towards the east (if set to 0, it will be calculated
                      # as (150. / (7. / dt)))
            'eddy_scale_min': 0.75, # minimum factor by which eddy amplitude
                                    # and area can change in one timestep
            'eddy_scale_max': 1.5, # maximum factor by which eddy amplitude
                                   # and area can change in one timestep
            'dict': 0, # dictionary containing detected eddies to be used when
                       # not stored in files (set to 0 otherwise)
            'data_path': datapath, # path to the detected eddies pickle files
            'file_root': 'test', # root name of the files, usually CONF-EXP etc.
            'file_spec': 'eddies_OW0.3', # part of the file name following the
                                         # datestring
            # the resulting file name that will be searched for is then
            # data_path+file_root+_+datestring+_+file_spec+.pickle
            # datestring will be defined inside the function
            'ross_path': datapath + '/' # path to rossrad.dat containing
                                        # Chelton et al. 1998 Rossby radii
            }
    un_items : list
        List of eddy indeces that are not assigned to a track yet.
    range_un_items : list
        Range of length of `un_items`.
    rossrad : dict
        Dictionary containing the 2D (lat, lon) first baroclinic Rossby
        radius 'rossby_rad', the first baroclinic wave speed 'c1' and
        the first baroclinic Rossby wave speed 'cR'.

    Returns
    -------
    is_near : list
        Boolean list of length `len(un_items)`. True for the eddies that are
        near the eddy in `track`, False otherwise.
    x0 : float
        Longitude of eddy in `track`.
    y0 : float
        Latitude of eddy in `track`.
    '''
    x0 = track['lon'][-1]  # [deg. lon] or [m]
    y0 = track['lat'][-1]  # [deg. lat] or [m]
    if trac_param['grid'] == 'latlon':
        d = calculate_d(trac_param['dE'], x0, y0, rossrad,
                        trac_param['dt'])  # [km]
        len_lon = len_deg_lon(y0)
        dE_in_ellipse = trac_param['dE'] / len_lon
        d_in_ellipse = d / len_lon
    elif trac_param['grid'] == 'cartesian':
        d = trac_param['dE']
        dE_in_ellipse = trac_param['dE'] * 1e3
        d_in_ellipse = d * 1e3
    # Find all eddy centroids in search region at time tt
    tmp_lon = [un_items[i]['lon']
               for i in range_un_items]
    tmp_lat = [un_items[i]['lat']
               for i in range_un_items]
    is_near = is_in_ellipse(x0, y0,
                            dE_in_ellipse,
                            d_in_ellipse,
                            tmp_lon, tmp_lat)
    return is_near, x0, y0


def eddy_is_similar(track, trac_param, un_items, range_un_items):
    '''Check if eddies' amp  and area are between a and b of original
    eddy. Where a and b are defined in `trac_param` as 'eddy_scale_min' and
    'eddy_scale_max', respectively.

    Parameters
    ----------
    track : dict
        Dictionary of an eddy track.
    trac_param : dict
        Dictionary with all the parameters needed for the eddy-tracking.
        The parameters are:
        trac_param = {
            'model': 'model_name', # either ORCA or MITgcm
            'grid': 'latlon', # either latlon or cartesian
            'start_time': 'YYYY-MM-DD', # time range start
            'end_time': 'YYYY-MM-DD', # time range end
            'calendar': 'standard', # calendar, must be either 360_day or
                                    # standard
            'dt': 5, # time step of the original fields
            'lon1': -180, # minimum longitude of detection region, either in
                          # the range (-180, 180) degrees or in m for a
                          # cartesian grid
            'lon2': -130, # maximum longitude of detection region, either
                          # (-180, 180) degrees or m
            'lat1': -55, # minimum latitude of detection region, either
                          # (-90, 90) degrees or m
            'lat2': -30, # maximum latitude of detection region, either
                          # (-90, 90) degrees or m
            'dE': 0., # maximum distance of search ellipsis from eddy center
                      # towards the east (if set to 0, it will be calculated
                      # as (150. / (7. / dt)))
            'eddy_scale_min': 0.75, # minimum factor by which eddy amplitude
                                    # and area can change in one timestep
            'eddy_scale_max': 1.5, # maximum factor by which eddy amplitude
                                   # and area can change in one timestep
            'dict': 0, # dictionary containing detected eddies to be used when
                       # not stored in files (set to 0 otherwise)
            'data_path': datapath, # path to the detected eddies pickle files
            'file_root': 'test', # root name of the files, usually CONF-EXP etc.
            'file_spec': 'eddies_OW0.3', # part of the file name following the
                                         # datestring
            # the resulting file name that will be searched for is then
            # data_path+file_root+_+datestring+_+file_spec+.pickle
            # datestring will be defined inside the function
            'ross_path': datapath + '/' # path to rossrad.dat containing
                                        # Chelton et al. 1998 Rossby radii
            }
    un_items : list
        List of eddy indeces that are not assigned to a track yet.
    range_un_items : list
        Range of length of `un_items`.

    Returns
    -------
    is_similar_amp : list
        Boolean list of length `len(un_items)`. True for the eddies that are
        of similar amplitude as the eddy in `track`, False otherwise.
    is_similar_area : list
        Boolean list of length `len(un_items)`. True for the eddies that are
        of similar area as the eddy in `track`, False otherwise.
    '''
    amp = track['amp'][-1]
    area = track['area'][-1]
    is_similar_amp = np.array([(un_items[i]['amp'] < amp
                                * trac_param['eddy_scale_max'])
                               * (un_items[i]['amp'] > amp
                                  * trac_param['eddy_scale_min'])
                               for i in range_un_items])
    is_similar_area = np.array([(un_items[i]['area'] < area
                                 * trac_param['eddy_scale_max'])
                                * (un_items[i]['area'] > area
                                   * trac_param['eddy_scale_min'])
                                for i in range_un_items])
    return is_similar_amp, is_similar_area


def eddy_is_same_type(track, un_items, range_un_items):
    '''Check if eddies' type is the same as original eddy.

    Parameters
    ----------
    track : dict
        Dictionary of an eddy track.
    un_items : list
        List of eddy indeces that are not assigned to a track yet.
    range_un_items : list
        Range of length of `un_items`.

    Returns
    -------
    is_same_type : list
        Boolean list of length `len(un_items)`. True for the eddies that are
        the same type as the eddy in `track`, False otherwise.
    '''
    is_same_type = np.array([un_items[i]['type'] == track['type']
                             for i in range_un_items])[:, None]
    return is_same_type


def track_core(det_eddies, tracks, trac_param, terminated_list, rossrad):
    '''Core function for the tracking of eddies detected with `detection.py`.

    Parameters
    ----------
    det_eddies : dict
        Dictionary of detected eddies at current time step.
    tracks : list
        List of dictionaries containing the tracked eddies.
    trac_param : dict
        Dictionary with all the parameters needed for the eddy-tracking.
        The parameters are:
        trac_param = {
            'model': 'model_name', # either ORCA or MITgcm
            'grid': 'latlon', # either latlon or cartesian
            'start_time': 'YYYY-MM-DD', # time range start
            'end_time': 'YYYY-MM-DD', # time range end
            'calendar': 'standard', # calendar, must be either 360_day or
                                    # standard
            'dt': 5, # time step of the original fields
            'lon1': -180, # minimum longitude of detection region, either in
                          # the range (-180, 180) degrees or in m for a
                          # cartesian grid
            'lon2': -130, # maximum longitude of detection region, either
                          # (-180, 180) degrees or m
            'lat1': -55, # minimum latitude of detection region, either
                          # (-90, 90) degrees or m
            'lat2': -30, # maximum latitude of detection region, either
                          # (-90, 90) degrees or m
            'dE': 0., # maximum distance of search ellipsis from eddy center
                      # towards the east (if set to 0, it will be calculated
                      # as (150. / (7. / dt)))
            'eddy_scale_min': 0.75, # minimum factor by which eddy amplitude
                                    # and area can change in one timestep
            'eddy_scale_max': 1.5, # maximum factor by which eddy amplitude
                                   # and area can change in one timestep
            'dict': 0, # dictionary containing detected eddies to be used when
                       # not stored in files (set to 0 otherwise)
            'data_path': datapath, # path to the detected eddies pickle files
            'file_root': 'test', # root name of the files, usually CONF-EXP etc.
            'file_spec': 'eddies_OW0.3', # part of the file name following the
                                         # datestring
            # the resulting file name that will be searched for is then
            # data_path+file_root+_+datestring+_+file_spec+.pickle
            # datestring will be defined inside the function
            'ross_path': datapath + '/' # path to rossrad.dat containing
                                        # Chelton et al. 1998 Rossby radii
            }
    terminated_list : list
        List of all indeces of eddy tracks that have been terminated.
    rossrad : dict
        Dictionary containing the 2D (lat, lon) first baroclinic Rossby
        radius 'rossby_rad', the first baroclinic wave speed 'c1' and
        the first baroclinic Rossby wave speed 'cR'.

    Returns
    -------
    Appends to global variables `tracks` and `terminated_list`.
    '''
    # Now, none of the eddies in `det_eddies` have been assigned to a track.
    unassigned = list(range(len(det_eddies)))

    # For each existing eddy (t<tt) that has not been terminated, loop through
    # the unassigned eddies and assign to existing eddy if appropriate
    #
    # First we construct a list of all existing eddies
    eddy_list = list(range(len(tracks)))
    # Now we remove all terminated eddies from that list
    [eddy_list.remove(terminated_list[i]) for i in range(len(terminated_list))]
    for ed in eddy_list:
        # Check if eddy has already been terminated (just a safety measure,
        # terminated eddies should not be in `eddy_list` any more...)
        if not tracks[ed]['terminated']:
            # Get all unassigned eddies from `det_eddies`
            get_item = operator.itemgetter(*unassigned)
            tmp_items = get_item(det_eddies)
            try:
                test = tmp_items[0]
                un_items = tmp_items
            except:
                un_items = {}
                un_items[0] = tmp_items
            range_un_items = range(0, len(un_items))

            # Test whether any eddies in `un_items` are near `tracks[ed]`
            is_near, x0, y0 = eddy_is_near(tracks[ed], trac_param,
                                           un_items, range_un_items, rossrad)
            if is_near.any():
                # If there are eddies near `tracks[ed]`, get their indeces and
                # update `un_items` and `range_un_items`
                is_near_index = np.where(is_near)[0]
                get_item = operator.itemgetter(*is_near_index)
                un_items = get_item(un_items)
                if not np.shape(un_items):
                    un_items = (un_items,)
                    range_un_items = range(0, len(un_items))
                else:
                    range_un_items = range(0, len(un_items))
            else:
                # If no eddy is near, terminate the track, append index to
                # `terminated_list` and jump to next eddy.
                tracks[ed]['terminated'] = True
                terminated_list.append(ed)
                continue

            # Test whether any eddies in `un_items` are similar to `tracks[ed]`
            is_similar_amp, is_similar_area = eddy_is_similar(tracks[ed],
                                                              trac_param,
                                                              un_items,
                                                              range_un_items)
            if is_similar_area.any():
                # If there are eddies similar to `tracks[ed]`, get their
                # indeces and update `un_items` and `range_un_items`
                is_similar_index = np.where(is_similar_area)[0]
                get_item = operator.itemgetter(*is_similar_index)
                un_items = get_item(un_items)
                if not np.shape(un_items):
                    un_items = (un_items,)
                    range_un_items = range(0, len(un_items))
                else:
                    range_un_items = range(0, len(un_items))
            else:
                # If no eddy is similar, terminate the track, append index to
                # `terminated_list` and jump to next eddy.
                tracks[ed]['terminated'] = True
                terminated_list.append(ed)
                continue

            # Test whether any eddies in `un_items` are the same type as
            # `tracks[ed]`
            is_same_type = eddy_is_same_type(tracks[ed],
                                             un_items, range_un_items)
            if is_same_type.any():
                # If there are eddies of the same type as `tracks[ed]`, get
                # their indeces and update `un_items` and `range_un_items`
                is_same_type_index = np.where(is_same_type)[0]
                get_item = operator.itemgetter(*is_same_type_index)
                un_items = get_item(un_items)
                if not np.shape(un_items):
                    un_items = (un_items,)
                    range_un_items = range(0, len(un_items))
                else:
                    range_un_items = range(0, len(un_items))
            else:
                # If no eddy is of the same type, terminate the track, append
                # index to `terminated_list` and jump to next eddy
                tracks[ed]['terminated'] = True
                terminated_list.append(ed)
                continue

            # Possible eddies are those which are near, of the right
            # amplitude, and of the same type
            possibles = is_near_index[is_similar_index[is_same_type_index]]

            if possibles.sum() > 0:
                # Of all found eddies, accept only the nearest one
                dist = np.array(
                    [np.sqrt((x0 - un_items[i]['lon']) ** 2
                     + (y0 - un_items[i]['lat']) ** 2)
                     for i in range_un_items])
                nearest = int(np.where(dist == np.min(dist))[0])
                nearest_eddy = is_near_index[is_similar_index[
                                   is_same_type_index[nearest]]]
                next_eddy = unassigned[nearest_eddy]

                # Add coordinates and properties of accepted eddy to
                # trajectory of eddy ed
                tracks[ed]['lon'] = np.append(
                    tracks[ed]['lon'], det_eddies[next_eddy]['lon'])
                tracks[ed]['lat'] = np.append(
                    tracks[ed]['lat'], det_eddies[next_eddy]['lat'])
                tracks[ed]['amp'] = np.append(
                    tracks[ed]['amp'], det_eddies[next_eddy]['amp'])
                tracks[ed]['area'] = np.append(
                    tracks[ed]['area'], det_eddies[next_eddy]['area'])
                tracks[ed]['scale'] = np.append(
                    tracks[ed]['scale'],
                    det_eddies[next_eddy]['scale'])
                tracks[ed]['time'] = np.append(
                    tracks[ed]['time'], det_eddies[next_eddy]['time'])
                tracks[ed]['eddy_i'][len(tracks[ed]['eddy_i'])] =\
                    det_eddies[next_eddy]['eddy_i']
                tracks[ed]['eddy_j'][len(tracks[ed]['eddy_j'])] =\
                    det_eddies[next_eddy]['eddy_j']
                # Remove detected eddy from list of eddies available for
                # assigment to existing trajectories
                unassigned.remove(next_eddy)
            # Terminate eddy if no possible candidate is found
            else:
                tracks[ed]['terminated'] = True
                terminated_list.append(ed)
    if len(unassigned) > 0:
        # If there are unassigned eddies left after looping through all tracks,
        # then make them the start of a new track.
        for un in unassigned:
            tmp_track = {}
            tmp_track['lon'] = np.array(det_eddies[un]['lon'])
            tmp_track['lat'] = np.array(det_eddies[un]['lat'])
            tmp_track['amp'] = np.array(det_eddies[un]['amp'])
            tmp_track['area'] = np.array(det_eddies[un]['area'])
            tmp_track['scale'] = np.array(det_eddies[un]['scale'])
            tmp_track['eddy_i'] = {}
            tmp_track['eddy_j'] = {}
            tmp_track['eddy_i'][0] = np.array(det_eddies[un]['eddy_i'])
            tmp_track['eddy_j'][0] = np.array(det_eddies[un]['eddy_j'])
            tmp_track['type'] = det_eddies[un]['type']
            tmp_track['time'] = det_eddies[un]['time']
            tmp_track['exist_at_start'] = False
            tmp_track['terminated'] = False
            tracks.append(tmp_track)


def track(tracking_params, in_file=True):
    ''' Eddy tracking based on similarity

    Parameters
    ----------
    trac_param : dict
        Dictionary with all the parameters needed for the eddy-tracking.
        The parameters are:
        trac_param = {
            'model': 'model_name', # either ORCA or MITgcm
            'grid': 'latlon', # either latlon or cartesian
            'start_time': 'YYYY-MM-DD', # time range start
            'end_time': 'YYYY-MM-DD', # time range end
            'calendar': 'standard', # calendar, must be either 360_day or
                                    # standard
            'dt': 5, # time step of the original fields
            'lon1': -180, # minimum longitude of detection region, either in
                          # the range (-180, 180) degrees or in m for a
                          # cartesian grid
            'lon2': -130, # maximum longitude of detection region, either
                          # (-180, 180) degrees or m
            'lat1': -55, # minimum latitude of detection region, either
                          # (-90, 90) degrees or m
            'lat2': -30, # maximum latitude of detection region, either
                          # (-90, 90) degrees or m
            'dE': 0., # maximum distance of search ellipsis from eddy center
                      # towards the east (if set to 0, it will be calculated
                      # as (150. / (7. / dt)))
            'eddy_scale_min': 0.75, # minimum factor by which eddy amplitude
                                    # and area can change in one timestep
            'eddy_scale_max': 1.5, # maximum factor by which eddy amplitude
                                   # and area can change in one timestep
            'dict': 0, # dictionary containing detected eddies to be used when
                       # not stored in files (set to 0 otherwise)
            'data_path': datapath, # path to the detected eddies pickle files
            'file_root': 'test', # root name of the files, usually CONF-EXP etc.
            'file_spec': 'eddies_OW0.3', # part of the file name following the
                                         # datestring
            # the resulting file name that will be searched for is then
            # data_path+file_root+_+datestring+_+file_spec+.pickle
            # datestring will be defined inside the function
            'ross_path': datapath + '/' # path to rossrad.dat containing
                                        # Chelton et al. 1998 Rossby radii
            }

    in_file : bool
        If true, detected eddies are loaded from file with the filename
        'trac_param['data_path'] + trac_param['file_root'] + '_'
         + str(datestring) + '_' + trac_param['file_spec'] + '.pickle'
         `datestring` is created from the `time` value of the eddy. If false,
         the dictionary trac_param['dict'] will be used for tracking.

    Returns
    -------
    tracks_dict : dict
        Dictionary containing the information of tracked eddies.
        `tracks` has the form:
        tracks = {e: {'exist_at_start': bool, # eddy exists at t=0
                      'terminated': bool, # eddy track terminates at t
                      'time': array, # time stamps
                      'type': str, # 'cyclonic' or 'anticyclonic'
                      'lon': array, # central longitude
                      'lat': array, # central latitude
                      'scale': array, # diameter of the eddy
                      'area': array, # area of the eddy
                      'amp': array, # amplitude
                      'eddy_i': array, # i-indeces of the eddy
                      'eddy_j': array # j-indeces of the eddy
                      }}
        where `e` is the eddy number.
    '''
    # Preparation with `prepare()`
    eddies_time, rossrad, trac_param = prepare(tracking_params)
    # Initialize `tracks` with all eddies at t=0
    terminated_list = []
    tracks = []
    if in_file:
        t = 0
        didntwork = True
        while didntwork:
            try:
                firstdate = str(eddies_time[t])[0:10]
                os.path.isfile(trac_param['data_path']
                               + trac_param['file_root'] + '_'
                               + str(firstdate) + '_'
                               + trac_param['file_spec']
                               + '.pickle')
                didntwork = False
            except:
                t += 1
                didntwork = True
                if t > len(eddies_time):
                    break
        if didntwork:
            print('no eddies found to track')
            return
        datestring = firstdate
        with open(trac_param['data_path'] + trac_param['file_root'] + '_'
                  + str(firstdate) + '_' + trac_param['file_spec']
                  + '.pickle',
                  'rb') as f:
            det_eddies = pickle.load(f)
            for ed in np.arange(0, len(det_eddies) - 1):
                tracks.append(det_eddies[ed].copy())
                tracks[ed]['exist_at_start'] = True
                tracks[ed]['terminated'] = False
                tracks[ed]['eddy_i'] = {}
                tracks[ed]['eddy_j'] = {}
                tracks[ed]['eddy_i'][0] = det_eddies[ed]['eddy_i']
                tracks[ed]['eddy_j'][0] = det_eddies[ed]['eddy_j']
        f.close()
    else:
        t = 0
        didntwork = True
        while didntwork:
            try:
                firstdate = trac_param['dict'][t][0]['time']
                didntwork = False
            except:
                t += 1
                didntwork = True
                if t > len(eddies_time):
                    break
        if didntwork:
            print('no eddies found to track')
            return
        det_eddies = trac_param['dict'][t]
        for ed in np.arange(0, len(det_eddies) - 1):
            tracks.append(det_eddies[ed].copy())
            tracks[ed]['exist_at_start'] = True
            tracks[ed]['terminated'] = False
            tracks[ed]['eddy_i'] = {}
            tracks[ed]['eddy_j'] = {}
            tracks[ed]['eddy_i'][0] = det_eddies[ed]['eddy_i']
            tracks[ed]['eddy_j'][0] = det_eddies[ed]['eddy_j']
    terminate_all = False
    for tt in np.arange(t + 1, len(eddies_time)):
        steps = np.around(np.linspace(0, len(eddies_time), 10))
        if tt in steps:
            print('tracking at time step ', str(tt + 1), ' of ',
                  len(eddies_time))
        if in_file:
            nextdate = str(eddies_time[tt])[0:10]
            file_found = os.path.isfile(trac_param['data_path']
                             + trac_param['file_root'] + '_'
                             + str(nextdate) + '_'
                             + trac_param['file_spec']
                             + '.pickle')
            if file_found:
                terminate_all = False
            else:
                terminate_all = True
        else:
            try:
                trac_param['dict'][tt][0]['time']
            except:
                terminate_all = True
        if terminate_all:
            for ed in range(len(tracks)):
                tracks[ed]['terminated'] = True
                terminated_list.append(ed)
            terminated_list = list(set(terminated_list))
            continue
        # Loop through all time steps in `det_eddies`
        if in_file:
            datestring = str(eddies_time[tt])[0:10]
            with open(trac_param['data_path'] + trac_param['file_root'] + '_'
                      + str(datestring) + '_' + trac_param['file_spec']
                      + '.pickle',
                      'rb') as f:
                det_eddies = pickle.load(f)
                track_core(det_eddies, tracks, trac_param,
                           terminated_list, rossrad)
            f.close()
        else:
            det_eddies = trac_param['dict'][tt]
            track_core(det_eddies, tracks, trac_param,
                       terminated_list, rossrad)
        terminate_all = False
    # Now remove all tracks of length 1 from `tracks` (a track is only
    # considered as such, if the eddy can be tracked over at least 2
    # consecutive time steps)
    tracks_dict = {}
    td_index = 0
    for ed in np.arange(0, len(tracks)):
        if len(tracks[ed]['lon']) > 1:
            tracks_dict[td_index] = tracks[ed]
            td_index = td_index + 1
    return tracks_dict


def split_track(tracking_params, in_file=True, continuing=False,
                tracks=[], terminated_list=[]):
    ''' Eddy tracking based on similarity with the possibility to split up
    the tracking into several parts.

    Parameters
    ----------
    trac_param : dict
        Dictionary with all the parameters needed for the eddy-tracking.
        The parameters are:
        trac_param = {
            'model': 'model_name', # either ORCA or MITgcm
            'grid': 'latlon', # either latlon or cartesian
            'start_time': 'YYYY-MM-DD', # time range start
            'end_time': 'YYYY-MM-DD', # time range end
            'calendar': 'standard', # calendar, must be either 360_day or
                                    # standard
            'dt': 5, # time step of the original fields
            'lon1': -180, # minimum longitude of detection region, either in
                          # the range (-180, 180) degrees or in m for a
                          # cartesian grid
            'lon2': -130, # maximum longitude of detection region, either
                          # (-180, 180) degrees or m
            'lat1': -55, # minimum latitude of detection region, either
                          # (-90, 90) degrees or m
            'lat2': -30, # maximum latitude of detection region, either
                          # (-90, 90) degrees or m
            'dE': 0., # maximum distance of search ellipsis from eddy center
                      # towards the east (if set to 0, it will be calculated
                      # as (150. / (7. / dt)))
            'eddy_scale_min': 0.75, # minimum factor by which eddy amplitude
                                    # and area can change in one timestep
            'eddy_scale_max': 1.5, # maximum factor by which eddy amplitude
                                   # and area can change in one timestep
            'dict': 0, # dictionary containing detected eddies to be used when
                       # not stored in files (set to 0 otherwise)
            'data_path': datapath, # path to the detected eddies pickle files
            'file_root': 'test', # root name of the files, usually CONF-EXP etc.
            'file_spec': 'eddies_OW0.3', # part of the file name following the
                                         # datestring
            # the resulting file name that will be searched for is then
            # data_path+file_root+_+datestring+_+file_spec+.pickle
            # datestring will be defined inside the function
            'ross_path': datapath + '/' # path to rossrad.dat containing
                                        # Chelton et al. 1998 Rossby radii
            }

    in_file : bool
        If true, detected eddies are loaded from file with the filename
        'trac_param['data_path'] + trac_param['file_root'] + '_'
         + str(datestring) + '_' + trac_param['file_spec'] + '.pickle'
         `datestring` is created from the `time` value of the eddy. If false,
         the dictionary trac_param['dict'] will be used for tracking.
    continuing : bool
        If True, tracking is assumed to continue from an earlier instance of
        tracking and the variables tracks and terminated_list need to be
        provided. Default is False, assuming that this is the first instance of
        tracking.
    tracks : dict
        If continuing is True, the `tracks` dictionary of the previous instance
        of `split_track()` needs to be provided.
    terminated_list : list
        If continuing is True, the `terminated_list` list of the previous
        instance of `split_track()` needs to be provided.

    Returns
    -------
    tracks_dict : dict
        Dictionary containing the information of tracked eddies.
        `tracks` has the form:
        tracks = {e: {'exist_at_start': bool, # eddy exists at t=0
                      'terminated': bool, # eddy track terminates at t
                      'time': array, # time stamps
                      'type': str, # 'cyclonic' or 'anticyclonic'
                      'lon': array, # central longitude
                      'lat': array, # central latitude
                      'scale': array, # diameter of the eddy
                      'area': array, # area of the eddy
                      'amp': array, # amplitude
                      'eddy_i': array, # i-indeces of the eddy
                      'eddy_j': array # j-indeces of the eddy
                      }}
        where `e` is the eddy number.
    tracks : dict
        Dictionary containing information of tracked eddies. As tracks_dict but
        containing all eddies (even tracks that are just one time step long) to
        enable continuation of tracking later on.
    terminated_list : list
        List containing the numbers of terminated tracks that is needed to continue tracking later on.
    '''
    # Preparation with `prepare()`
    eddies_time, rossrad, trac_param = prepare(tracking_params)
    # Initialize `tracks` with all eddies at t=0
    if continuing:
        t = 0
        if not in_file:
            while (str(trac_param['dict'][t][0]['time']) != eddies_time[0]):
                t += 1
        t_range = np.arange(t, t + len(eddies_time))
        terminate_all = False
    else:
        if in_file:
            t = 0
            didntwork = True
            while didntwork:
                try:
                    firstdate = str(eddies_time[t])[0:10]
                    os.path.isfile(trac_param['data_path']
                                   + trac_param['file_root'] + '_'
                                   + str(firstdate) + '_'
                                   + trac_param['file_spec']
                                   + '.pickle')
                    didntwork = False
                except:
                    t += 1
                    didntwork = True
                    if t > len(eddies_time):
                        break
            if didntwork:
                print('no eddies found to track')
                return
            datestring = firstdate
            with open(trac_param['data_path'] + trac_param['file_root'] + '_'
                      + str(firstdate) + '_' + trac_param['file_spec']
                      + '.pickle',
                      'rb') as f:
                det_eddies = pickle.load(f)
                for ed in np.arange(0, len(det_eddies) - 1):
                    tracks.append(det_eddies[ed].copy())
                    tracks[ed]['exist_at_start'] = True
                    tracks[ed]['terminated'] = False
                    tracks[ed]['eddy_i'] = {}
                    tracks[ed]['eddy_j'] = {}
                    tracks[ed]['eddy_i'][0] = det_eddies[ed]['eddy_i']
                    tracks[ed]['eddy_j'][0] = det_eddies[ed]['eddy_j']
            f.close()
        else:
            t = 0
            while (str(trac_param['dict'][t][0]['time']) != eddies_time[0]):
                t += 1
            didntwork = True
            while didntwork:
                try:
                    firstdate = trac_param['dict'][t][0]['time']
                    didntwork = False
                except:
                    t += 1
                    didntwork = True
                    if t > len(eddies_time):
                        break
            if didntwork:
                print('no eddies found to track')
                return
            det_eddies = trac_param['dict'][t]
            for ed in np.arange(0, len(det_eddies) - 1):
                tracks.append(det_eddies[ed].copy())
                tracks[ed]['exist_at_start'] = True
                tracks[ed]['terminated'] = False
                tracks[ed]['eddy_i'] = {}
                tracks[ed]['eddy_j'] = {}
                tracks[ed]['eddy_i'][0] = det_eddies[ed]['eddy_i']
                tracks[ed]['eddy_j'][0] = det_eddies[ed]['eddy_j']
        terminate_all = False
        t_range = np.arange(t + 1, len(eddies_time))
    for tt in t_range:
        steps = np.around(np.linspace(0, len(eddies_time), 10))
        if tt in steps:
            print('tracking at time step ', str(tt + 1), ' of ',
                  len(eddies_time))
        if in_file:
            nextdate = str(eddies_time[tt])[0:10]
            file_found = os.path.isfile(trac_param['data_path']
                             + trac_param['file_root'] + '_'
                             + str(nextdate) + '_'
                             + trac_param['file_spec']
                             + '.pickle')
            if file_found:
                terminate_all = False
            else:
                terminate_all = True
        else:
            try:
                trac_param['dict'][tt][0]['time']
            except:
                terminate_all = True
        if terminate_all:
            for ed in range(len(tracks)):
                tracks[ed]['terminated'] = True
                terminated_list.append(ed)
            terminated_list = list(set(terminated_list))
            continue
        # Loop through all time steps in `det_eddies`
        if in_file:
            datestring = str(eddies_time[tt])[0:10]
            with open(trac_param['data_path'] + trac_param['file_root'] + '_'
                      + str(datestring) + '_' + trac_param['file_spec']
                      + '.pickle',
                      'rb') as f:
                det_eddies = pickle.load(f)
                track_core(det_eddies, tracks, trac_param,
                           terminated_list, rossrad)
            f.close()
        else:
            det_eddies = trac_param['dict'][tt]
            track_core(det_eddies, tracks, trac_param,
                       terminated_list, rossrad)
        terminate_all = False
    # Now remove all tracks of length 1 from `tracks` (a track is only
    # considered as such, if the eddy can be tracked over at least 2
    # consecutive time steps)
    tracks_dict = {}
    td_index = 0
    for ed in np.arange(0, len(tracks)):
        if len(tracks[ed]['lon']) > 1:
            tracks_dict[td_index] = tracks[ed]
            td_index = td_index + 1
    return tracks_dict, tracks, terminated_list
