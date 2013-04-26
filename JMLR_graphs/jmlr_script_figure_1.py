import argparse
import datetime
#
import pylab
import numpy
#
import tabular_predDB.cython_code.State as State
import tabular_predDB.python_utils.data_utils as du
import tabular_predDB.python_utils.file_utils as fu


# parse input
parser = argparse.ArgumentParser()
parser.add_argument('--gen_seed', default=0, type=int)
parser.add_argument('--inf_seed', default=0, type=int)
parser.add_argument('--num_clusters', default=10, type=int)
parser.add_argument('--num_cols', default=100, type=int)
parser.add_argument('--num_rows', default=1000, type=int)
parser.add_argument('--num_views', default=1, type=int)
parser.add_argument('--num_iters', default=100, type=int)
parser.add_argument('--max_mean', default=10, type=float)
parser.add_argument('--max_std', default=0.3, type=float)
parser.add_argument('--N_GRID', default=31, type=int)
args = parser.parse_args()
#
gen_seed = args.gen_seed
inf_seed = args.inf_seed
num_clusters = args.num_clusters
num_cols = args.num_cols
num_rows = args.num_rows
num_views = args.num_views
num_iters = args.num_iters
max_mean = args.max_mean
max_std = args.max_std
N_GRID = args.N_GRID


str_args = (num_views, gen_seed, inf_seed)
save_filename_prefix = 'num_views_%s_gen_seed_%s_inf_seed_%s' % str_args


# helper functions
def get_num_views(p_State):
    return len(p_State.get_X_D())

def get_seconds_since(dt):
    delta = datetime.datetime.now() - dt
    return delta.total_seconds()

# create the data
T, M_r, M_c = du.gen_factorial_data_objects(
    gen_seed, num_clusters,
    num_cols, num_rows, num_views,
    max_mean=max_mean, max_std=max_std,
    )

num_views_list_dict = dict()
seconds_since_start_list_dict = dict()
valid_initializers = set(["together", "from_the_prior", "apart"])
for initialization in valid_initializers:
    # include state creation time in first iter
    start_dt = datetime.datetime.now()
    # create the state
    p_State = State.p_State(M_c, T, N_GRID=N_GRID, SEED=inf_seed,
                            initialization=initialization)
    #p_State.plot_T(filename='T')
    #p_State.plot(filename='X_D_000')
    num_views_list = [get_num_views(p_State)]
    seconds_since_start_list = [0.]
    for iter_idx in range(num_iters):
        p_State.transition()
        num_views_list.append(get_num_views(p_State))
        seconds_since_start_list.append(get_seconds_since(start_dt))
    num_views_list_dict[initialization] = num_views_list
    seconds_since_start_list_dict[initialization] = seconds_since_start_list

to_pickle = dict(
    num_views_list_dict=num_views_list_dict,
    seconds_since_start_list_dict=seconds_since_start_list_dict,
    )
fu.pickle(to_pickle, save_filename_prefix + '.pkl.gz')


fh = pylab.figure()
#
pylab.subplot(211)
for initialization in valid_initializers:
    seconds_since_start_list = seconds_since_start_list_dict[initialization]
    iter_idx = range(len(seconds_since_start_list))
    num_views_list = num_views_list_dict[initialization]
    pylab.plot(iter_idx, num_views_list)
pylab.xlabel('iteration #')
pylab.ylabel('num_views')
pylab.legend(list(valid_initializers))
#
pylab.subplot(212)
for initialization in valid_initializers:
    seconds_since_start_list = seconds_since_start_list_dict[initialization]
    num_views_list = num_views_list_dict[initialization]
    pylab.plot(seconds_since_start_list, num_views_list)
pylab.xlabel('cumulative run time (seconds)')
pylab.ylabel('num_views')
pylab.legend(list(valid_initializers))
pylab.savefig(save_filename_prefix)
