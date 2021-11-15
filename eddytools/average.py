'''average

Collection of functions to average the sampled eddies from `sample.py`.

'''

import numpy as np
from scipy.interpolate import interp1d


def interp(sampled, v, t, lon_interp, method, anom=True):
    '''Interpolate the normalized longitudes onto a common vector.

    Parameters
    ----------
    sampled : dict
        Dictionary containing the eddies to be averaged.
    v : str
        Name of the variable to interpolate.
    t : int
        Time step in `sampled` to interpolate.
    lon_interp : array
        Longitude values to interpolate to
    anom : bool
        Whether or not the anomalies should be interpolated. Default is True.

     Returns
    -------
    interpolated : array
        Section of `v` interpolated onto common normalized longitude
        vector.
    '''
    if anom:
        if len(np.shape(sampled[v + '_sec'].isel(time=t).squeeze())) == 2:
            interp_lon = interp1d(
                sampled[v + '_sec_norm_lon'].isel(time=t)
                .dropna('sec_index', how='all'),
                sampled[v + '_sec'].isel(time=t)
                .dropna('sec_index', how='all').squeeze()
                - sampled[v + '_around'].isel(time=t),
                axis=1, fill_value="extrapolate", kind=method
                )
        elif len(np.shape(sampled[v + '_sec'].isel(time=t).squeeze())) == 1:
            interp_lon = interp1d(
                sampled[v + '_sec_norm_lon'].isel(time=t)
                .dropna('sec_index', how='all'),
                sampled[v + '_sec'].isel(time=t)
                .dropna('sec_index', how='all').squeeze()
                - sampled[v + '_around'].isel(time=t),
                axis=0, fill_value="extrapolate", kind=method
                )
    else:
        if len(np.shape(sampled[v + '_sec'].isel(time=t).squeeze())) == 2:
            interp_lon = interp1d(
                sampled[v + '_sec_norm_lon'].isel(time=t)
                .dropna('sec_index', how='all'),
                sampled[v + '_sec'].isel(time=t)
                .dropna('sec_index', how='all').squeeze(),
                axis=1, fill_value="extrapolate", kind=method
                )
        elif len(np.shape(sampled[v + '_sec'].isel(time=t).squeeze())) == 1:
            interp_lon = interp1d(
                sampled[v + '_sec_norm_lon'].isel(time=t)
                .dropna('sec_index', how='all'),
                sampled[v + '_sec'].isel(time=t)
                .dropna('sec_index', how='all').squeeze(), axis=0,
                fill_value="extrapolate", kind=method
                )
    return interp_lon(lon_interp)


def prepare(sampled, vars, lon_int=101, method='nearest'):
    ''' Preparation for the averaging of eddy sections to construct a mean
    eddy (that still has a temporal evolution). Only anomalies to the eddy's
    surrounding are considered.

    Parameters
    ----------
    sampled : dict
        Dictionary containing the eddies to be averaged.
    vars : dict
        Variables to average for every single eddy.
    lon_int : int
        Length of the normalized longitude vector to interpolate to.
    method : str
        Interpolation method.

    Returns
    -------
    aves : dict
        Dictionary containing an array for every variables in `vars`, sorted
        by months that can then be averaged. aves[v][m] = arr, where v in
        `vars`, m in ['01', '02', ... , '12']. The arrays `arr` have the
        dimensions `(e, t, z, x)`, where `e` is the eddy number, `t` is the
        time step, `z` is the depth, and `x` is the longitude.
    '''
    lon_interp = np.linspace(-0.5, 0.5, lon_int)
    len_z = len(sampled[1]['depth'])
    max_time = 0
    for ed in np.arange(1, len(sampled) + 1):
        if len(sampled[ed]['time']) > max_time:
            max_time = len(sampled[ed]['time'])
    aves = {}
    for v in vars:
        print(v)
        aves[v + '_anom'] = {}
        aves[v] = {}
        aves[v + '_around'] = {}
        for ed in np.arange(1, len(sampled) + 1):
            month = str(sampled[ed]['time'][0].values)[5:7]
            if len(np.shape(sampled[ed][v + '_sec'][0].squeeze())) == 2:
                try:
                    aves[v + '_anom'][month] =\
                        np.vstack(
                            (aves[v + '_anom'][month],
                             np.zeros((1, max_time,
                                       len_z, len(lon_interp))) + np.nan)
                            )
                    aves[v][month] =\
                        np.vstack(
                            (aves[v][month],
                             np.zeros((1, max_time,
                                       len_z, len(lon_interp))) + np.nan)
                            )
                    aves[v + '_around'][month] =\
                        np.vstack(
                            (aves[v + '_around'][month],
                             np.zeros((1, max_time,
                                       len_z)) + np.nan)
                            )
                except:
                    aves[v + '_anom'][month] =\
                        np.zeros((1, max_time, len_z,
                                  len(lon_interp))) + np.nan
                    aves[v][month] =\
                        np.zeros((1, max_time, len_z,
                                  len(lon_interp))) + np.nan
                    aves[v + '_around'][month] =\
                        np.zeros((1, max_time, len_z)) + np.nan
                e = np.shape(aves[v + '_anom'][month])[0] - 1
                for m in np.arange(0, len(sampled[ed]['time'])):
                    aves[v + '_anom'][month][e, m, :, :] =\
                        interp(sampled[ed], v, m, method=method anom=True)
                    aves[v][month][e, m, :, :] =\
                        interp(sampled[ed], v, m, method=method anom=False)
                    aves[v + '_around'][month][e, m, :] =\
                        sampled[ed][v + '_around'][m]
            elif len(np.shape(sampled[ed][v + '_sec'][0].squeeze())) == 1:
                try:
                    aves[v + '_anom'][month] =\
                        np.vstack(
                            (aves[v + '_anom'][month],
                             np.zeros((1, max_time,
                                       len(lon_interp))) + np.nan)
                             )
                    aves[v][month] =\
                        np.vstack(
                            (aves[v][month],
                             np.zeros((1, max_time,
                                       len(lon_interp))) + np.nan)
                             )
                    aves[v + '_around'][month] =\
                        np.vstack(
                            (aves[v + '_around'][month],
                             np.zeros((1, max_time)) + np.nan)
                             )
                except:
                    aves[v + '_anom'][month] =\
                        np.zeros((1, max_time, len(lon_interp))) + np.nan
                    aves[v][month] =\
                        np.zeros((1, max_time, len(lon_interp))) + np.nan
                    aves[v + '_around'][month] =\
                        np.zeros((1, max_time)) + np.nan
                e = np.shape(aves[v + '_anom'][month])[0] - 1
                for m in np.arange(0, len(sampled[ed]['time'])):
                    aves[v + '_anom'][month][e, m, :] =\
                        interp(sampled[ed], v, m, method=method, anom=True)
                    aves[v][month][e, m, :] =\
                        interp(sampled[ed], v, m, method=method, anom=False)
                    aves[v + '_around'][month][e, m] =\
                        sampled[ed][v + '_around'][m]
    return aves


def seasonal(eddies, variables):
    out = {}
    for meth in ['ave', 'evo']:
        out[meth] = {}
        for quant in ['count', 'mean', 'std']:
            out[meth][quant] = {}
            if quant == 'mean':

                def function(array):
                    return np.nanmean(array, axis=0)

            elif quant == 'std':

                def function(array):
                    return np.nanstd(array, axis=0)

            def c_function(array):
                return np.count_nonzero(~np.isnan(array), axis=0)

            for seas in ['DJF', 'MAM', 'JJA', 'SON']:
                out[meth][quant][seas] = {}
                if seas == 'DJF':
                    one = '12'
                    two = '01'
                    thr = '02'
                elif seas == 'MAM':
                    one = '03'
                    two = '04'
                    thr = '05'
                elif seas == 'JJA':
                    one = '06'
                    two = '07'
                    thr = '08'
                elif seas == 'SON':
                    one = '09'
                    two = '10'
                    thr = '11'
                for var in variables:
                    for m in [one, two, thr]:
                        crit = (np.abs(eddies[var + '_anom'][m])
                                > np.mean(np.abs(eddies[var + '_anom'][m]))
                                * 100)
                        eddies[var + '_anom'][m][crit] = np.nan
                        eddies[var][m][crit] = np.nan
                    if len(np.shape(eddies[var + '_anom'][one])) == 4:

                        def extract(array, meth):
                            if meth == 'ave':
                                ar = array[:, 0, :, :]
                            elif meth == 'evo':
                                ar = array[:, :, :, 50]
                            return ar

                        def extract_around(array):
                            ar = array[:, 0, :]
                            return ar

                    elif len(np.shape(eddies[var + '_anom'][one])) == 3:

                        def extract(array, meth):
                            if meth == 'ave':
                                ar = array[:, 0, :]
                            elif meth == 'evo':
                                ar = array[:, :, 50]
                            return ar

                        def extract_around(array):
                            ar = array[:, 0]
                            return ar

                    if quant == 'count':
                        out[meth][quant][seas][var + '_anom'] =\
                            (c_function(extract(
                                eddies[var + '_anom'][one], meth
                                ))
                             + c_function(extract(
                                 eddies[var + '_anom'][two], meth
                                 ))
                             + c_function(extract(
                                 eddies[var + '_anom'][thr], meth
                                 )))
                        out[meth][quant][seas][var] =\
                            (c_function(extract(
                                eddies[var][one], meth
                                ))
                             + c_function(extract(
                                 eddies[var][two], meth
                                 ))
                             + c_function(extract(
                                 eddies[var][thr], meth
                                 )))
                        out[meth][quant][seas][var + '_around'] =\
                            (c_function(extract_around(
                                eddies[var + '_around'][one]
                                ))
                             + c_function(extract_around(
                                 eddies[var + '_around'][two]
                                 ))
                             + c_function(extract_around(
                                 eddies[var + '_around'][thr]
                                 )))
                    else:
                        out[meth][quant][seas][var + '_anom'] =\
                            (((function(extract(
                                eddies[var + '_anom'][one], meth
                                ))
                               * c_function(extract(
                                   eddies[var + '_anom'][one], meth
                                   )))
                              + (function(extract(
                                  eddies[var + '_anom'][two], meth
                                  ))
                                 * c_function(extract(
                                     eddies[var + '_anom'][two], meth
                                     )))
                              + (function(extract(
                                  eddies[var + '_anom'][thr], meth
                                  ))
                                 * c_function(extract(
                                     eddies[var + '_anom'][thr], meth
                                     ))))
                             / out[meth]['count'][seas][var + '_anom'])
                        out[meth][quant][seas][var] =\
                            (((function(extract(
                                eddies[var][one], meth
                                ))
                               * c_function(extract(
                                   eddies[var][one], meth
                                   )))
                              + (function(extract(
                                  eddies[var][two], meth
                                  ))
                                 * c_function(extract(
                                     eddies[var][two], meth
                                     )))
                              + (function(extract(
                                  eddies[var][thr], meth
                                  ))
                                 * c_function(extract(
                                     eddies[var][thr], meth
                                     ))))
                             / out[meth]['count'][seas][var])
                        out[meth][quant][seas][var + '_around'] =\
                            (((function(extract_around(
                                eddies[var + '_around'][one]
                                ))
                               * c_function(extract_around(
                                   eddies[var + '_around'][one]
                                   )))
                              + (function(extract_around(
                                  eddies[var + '_around'][two]
                                  ))
                                 * c_function(extract_around(
                                     eddies[var + '_around'][two]
                                     )))
                              + (function(extract_around(
                                   eddies[var + '_around'][thr]
                                   ))
                                  * c_function(extract_around(
                                      eddies[var + '_around'][thr]
                                      ))))
                             / out[meth]['count'][seas][var + '_around'])
    return out


def monthly(eddies, variables):
    out = {}
    for meth in ['ave', 'evo']:
        out[meth] = {}
        for quant in ['mean', 'std', 'count']:
            out[meth][quant] = {}
            if quant == 'mean':

                def function(array):
                    return np.nanmean(array, axis=0)

            elif quant == 'std':

                def function(array):
                    return np.nanstd(array, axis=0)

            elif quant == 'count':

                def function(array):
                    return np.count_nonzero(~np.isnan(array), axis=0)

            for m in ['01', '02', '03', '04', '05', '06',
                      '07', '08', '09', '10', '11', '12']:
                out[meth][quant][m] = {}
                for var in variables:
                    crit = (np.abs(eddies[var + '_anom'][m])
                            > np.mean(np.abs(eddies[var + '_anom'][m]))
                            * 100)
                    eddies[var + '_anom'][m][crit] = np.nan
                    eddies[var][m][crit] = np.nan
                    if len(np.shape(eddies[var + '_anom'][m])) == 4:

                        def extract(array, meth):
                            if meth == 'ave':
                                ar = array[:, 0, :, :]
                            elif meth == 'evo':
                                ar = array[:, :, :, 50]
                            return ar

                        def extract_around(array):
                            ar = array[:, 0, :]
                            return ar

                    elif len(np.shape(eddies[var + '_anom'][m])) == 3:

                        def extract(array, meth):
                            if meth == 'ave':
                                ar = array[:, 0, :]
                            elif meth == 'evo':
                                ar = array[:, :, 50]
                            return ar

                        def extract_around(array):
                            ar = array[:, 0]
                            return ar

                    out[meth][quant][m][var + '_anom'] =\
                        function(extract(eddies[var + '_anom'][m], meth))
                    out[meth][quant][m][var] =\
                        function(extract(eddies[var][m], meth))
                    out[meth][quant][m][var + '_around'] =\
                        function(extract_around(eddies[var + '_around'][m]))
    return out


def total(eddies, variables):
    m_eddies = monthly(eddies, variables)
    out = {}
    for meth in ['ave', 'evo']:
        out[meth] = {}
        for quant in ['count', 'mean', 'std']:
            out[meth][quant] = {}
            for var in variables:
                if quant == 'count':
                    out[meth][quant][var + '_anom'] =\
                        m_eddies[meth][quant]['01'][var + '_anom']
                    out[meth][quant][var] =\
                        m_eddies[meth][quant]['01'][var]
                    out[meth][quant][var + '_around'] =\
                        m_eddies[meth][quant]['01'][var + '_around']
                else:
                    out[meth][quant][var + '_anom'] =\
                        (m_eddies[meth][quant]['01'][var + '_anom']
                         * m_eddies[meth]['count']['01'][var + '_anom'])
                    out[meth][quant][var] =\
                        (m_eddies[meth][quant]['01'][var]
                         * m_eddies[meth]['count']['01'][var])
                    out[meth][quant][var + '_around'] =\
                        (m_eddies[meth][quant]['01'][var + '_around']
                         * m_eddies[meth]['count']['01'][var + '_around'])
                for m in ['02', '03', '04', '05', '06',
                          '07', '08', '09', '10', '11', '12']:
                    if quant == 'count':
                        out[meth][quant][var + '_anom'] =\
                            (out[meth][quant][var + '_anom']
                             + m_eddies[meth][quant][m][var + '_anom'])
                        out[meth][quant][var] =\
                            (out[meth][quant][var]
                             + m_eddies[meth][quant][m][var])
                        out[meth][quant][var + '_around'] =\
                            (out[meth][quant][var + '_around']
                             + m_eddies[meth][quant][m][var + '_around'])
                    else:
                        out[meth][quant][var + '_anom'] =\
                            (out[meth][quant][var + '_anom']
                             + (m_eddies[meth][quant][m][var + '_anom']
                                * m_eddies[meth]['count'][m][var + '_anom']))
                        out[meth][quant][var] =\
                            (out[meth][quant][var]
                             + (m_eddies[meth][quant][m][var]
                                * m_eddies[meth]['count'][m][var]))
                        out[meth][quant][var + '_around'] =\
                            (out[meth][quant][var + '_around']
                             + (m_eddies[meth][quant][m][var + '_around']
                                * m_eddies[meth]['count'][m][var + '_around']))
                if (quant == 'mean') or (quant == 'std'):
                    out[meth][quant][var + '_anom'] =\
                        (out[meth][quant][var + '_anom']
                         / out[meth]['count'][var + '_anom'])
                    out[meth][quant][var] =\
                        (out[meth][quant][var]
                         / out[meth]['count'][var])
                    out[meth][quant][var + '_around'] =\
                        (out[meth][quant][var + '_around']
                         / out[meth]['count'][var + '_around'])
    return out
