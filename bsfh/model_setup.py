import sys, os, getopt, json
from copy import deepcopy
import numpy as np
from bsfh import parameters, sedmodel
from bsfh.datautils import fix_obs

"""This module has methods to take a .json or .py file containing run paramters,
model parameters and other info and return a parset, a model, and an
initial_params vector
"""

def parse_args(argv, argdict={'param_file':None, 'sps':'sps_basis',
                              'custom_filter_keys':None,
                              'compute_vega_mags':False}):
    """ Parse command line arguments, allowing for optional arguments.
    Simple/Fragile.
    """
    args = [sub for arg in argv[1:] for sub in arg.split('=')]
    for i, a in enumerate(args):
        if (a[:2] == '--'):
            abare = a[2:]
            if abare == 'help':
                show_syntax(argv, argdict)
                sys.exit()
        else:
            continue
        if abare in argdict.keys():
            apo = deepcopy(args[i+1])
            func = type(argdict[abare])
            try:
                argdict[abare] = func(apo)
            except TypeError:
                argdict[abare] = apo
    return argdict

def show_syntax(args, ad):
    """Show command line syntax corresponding to the provided arg
    dictionary `ad`.
    """
    print('Usage:\n {0} '.format(args[0]) +
          ' '.join(['--{0}=<value>'.format(k) for k in ad.keys()]))


def load_gp(use_george=False, **extras):
    """Return a GP object, either using BSFH's internal GP objects or
    George
    """
    if use_george:
        import george
        kernel = (george.kernels.WhiteKernel(0.0) +
                  0.0 * george.kernels.ExpSquaredKernel(0.0))
        gp = george.GP(kernel, solver=george.HODLRSolver)
    else:
        from bsfh.gp import GaussianProcess
        gp = GaussianProcess(kernel=np.array([0.0, 0.0, 0.0]))
    return gp
    
def load_sps(sptype=None, compute_vega_mags=False,
             zcontinuous=1, custom_filter_keys=None,
             **extras):
    """Return an sps object of the given type.
    """
    if sptype == 'sps_basis':
        from bsfh import sps_basis
        sps = sps_basis.StellarPopBasis(compute_vega_mags=compute_vega_mags)
    elif sptype == 'fsps':
        import fsps
        sps = fsps.StellarPopulation(zcontinuous=zcontinuous,
                                     compute_vega_mags=compute_vega_mags)
        if custom_filter_keys is not None:
            fsps.filters.FILTERS = custom_filter_dict(custom_filter_keys)
    else:
        print('No SPS type set')
        sys.exit(1)

    return sps
        
def load_model(filename, **extras):
    """Load the model object from a model config list
    """
    ext = filename.split('.')[-1]
    if ext == 'py':
        setup_module = load_module_from_file(filename)
        mp = deepcopy(setup_module.model_params)
        model_type = getattr(setup_module, 'model_type', sedmodel.SedModel)
    elif ext == 'json':
        rp, mp = parameters.read_plist(filename)
        model_type = getattr(sedmodel, rp.get('model_type','SedModel'))
    model = model_type(mp)
    return model

def run_params(filename, **kwargs):
    
    ext = filename.split('.')[-1]
    if ext == 'py':
        setup_module = load_module_from_file(filename)
        rp = deepcopy(setup_module.run_params)
    elif ext == 'json':
        rp, mp = parameters.read_plist(filename)
    for k, v in kwargs.iteritems():
        rp[k] = v
    
def load_obs(filename, run_params):
    """Load the obs dictionary
    """
    ext = filename.split('.')[-1]
    obs = None
    if ext == 'py':
        print('reading py script {}'.format(filename))
        setup_module = load_module_from_file(filename)
        obs = deepcopy(getattr(setup_module, 'obs', None))
    if obs is None:
        from bsfh import loadspec
        funcname = run_params['data_loading_function_name']
        obsfunction = getattr(loadspec, funcname)
        obs = obsfunction(**run_params)

    obs = fix_obs(obs, **run_params)
    return obs

def load_mock(filename, run_params, model, sps):
    """Load the obs dictionary using mock data.
    """
    from bsfh.datautils import generate_mock
    ext = filename.split('.')[-1]
    mock_info = None
    if ext == 'py':
        print('reading py script {}'.format(filename))
        setup_module = load_module_from_file(filename)
        mock_info = deepcopy(getattr(setup_module, 'mock_info', None))
    if mock_info is None:
        mock_info = run_params.get('mock_info', None)
    
    mockdat = generate_mock(model, sps, mock_info)
    mockdat = fix_obs(mockdat, **run_params)
    mockdat['mock_info'] = mock_info
    return mockdat

def load_module_from_file(path_to_file):
    """This has to break everything ever, right?
    """
    from importlib import import_module
    path, filename = os.path.split(path_to_file)
    modname = filename.replace('.py','')
    sys.path.insert(0,path)
    user_module = import_module(modname)
    sys.path.remove(path)
    return user_module

class Bunch(object):
    """ Simple storage.
    """
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

def custom_filter_dict(filename):
    filter_dict = {}
    with open(filename, 'r') as f:
        for line in f:
            ind, name = line.split()
            filter_dict[name.lower()] = Bunch(index = int(ind)-1)
            
    return filter_dict
