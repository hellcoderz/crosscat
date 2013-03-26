import sys
import copy
from collections import Counter
#
import numpy
#
import tabular_predDB.cython_code.ContinuousComponentModel as CCM
import tabular_predDB.cython_code.MultinomialComponentModel as MCM


class Bunch(dict):
    def __getattr__(self, key):
        if self.has_key(key):
            return self.get(key, None)
        else:
            raise AttributeError(key)
    def __setattr__(self, key, value):
        self[key] = value

Constraints = Bunch

def simple_predictive_sample(M_c, X_L, X_D, Y, Q, get_next_seed, n=1):
    num_rows = len(X_D[0])
    num_cols = len(M_c['column_metadata'])
    query_row = Q[0][0]
    query_columns = [query[1] for query in Q]
    # enforce query rows all same row
    assert(all([query[0]==query_row for query in Q]))
    # enforce query columns observed column
    assert(all([query_column<num_cols for query_column in query_columns]))
    is_observed_row = query_row < num_rows
    x = []
    if not is_observed_row:
        x = simple_predictive_sample_unobserved(
            M_c, X_L, X_D, Y, query_row, query_columns, get_next_seed, n)
    else:
        x = simple_predictive_sample_observed(
            M_c, X_L, X_D, Y, query_row, query_columns, get_next_seed, n)    
    # # more modular logic
    # observed_view_cluster_tuples = ()
    # if is_observed_row:
    #     observed_view_cluster_tuples = get_view_cluster_tuple(
    #         M_c, X_L, X_D, query_row)
    #     observed_view_cluster_tuples = [observed_view_cluster_tuples] * n
    # else:
    #     view_cluster_logps = determine_view_cluster_logps(
    #         M_c, X_L, X_D, Y, query_row)
    #     observed_view_cluster_tuples = \
    #         sample_view_cluster_tuples_from_logp(view_cluster_logps, n)
    # x = draw_from_view_cluster_tuples(M_c, X_L, X_D, Y,
    #                                   observed_view_cluster_tuples)
    return x

def simple_predictive_sample_observed(M_c, X_L, X_D, Y, which_row,
                                      which_columns, get_next_seed, n=1):
    get_which_view = lambda which_column: \
        X_L['column_partition']['assignments'][which_column]
    column_to_view = dict()
    for which_column in which_columns:
        column_to_view[which_column] = get_which_view(which_column)
    #
    view_to_cluster_model = dict()
    for which_view in list(set(column_to_view.values())):
        which_cluster = X_D[which_view][which_row]
        cluster_model = create_cluster_model_from_X_L(M_c, X_L, which_view,
                                                      which_cluster)
        view_to_cluster_model[which_view] = cluster_model
    #
    samples_list = []
    for sample_idx in range(n):
        this_sample_draws = []
        for which_column in which_columns:
            which_view = column_to_view[which_column]
            cluster_model = view_to_cluster_model[which_view]
            component_model = cluster_model[which_column]
            draw_constraints = get_draw_constraints(X_L, X_D, Y,
                                                    which_row, which_column)
            SEED = get_next_seed()
            draw = component_model.get_draw_constrained(SEED,
                                                        draw_constraints)
            this_sample_draws.append(draw)
        samples_list.append(this_sample_draws)
    return samples_list

def names_to_global_indices(column_names, M_c):
    name_to_idx = M_c['name_to_idx']
    # FIXME: str(column_name) is hack
    return [name_to_idx[str(column_name)] for column_name in column_names]

def extract_view_column_info(M_c, X_L, view_idx):
    view_state_i = X_L['view_state'][view_idx]
    column_names = view_state_i['column_names']
    column_component_suffstats = view_state_i['column_component_suffstats']
    # ensure view_state_i ordering matches global ordering
    global_column_indices = names_to_global_indices(column_names, M_c)
    column_metadata = numpy.array([
        M_c['column_metadata'][col_idx]
        for col_idx in global_column_indices
        ])
    column_hypers = numpy.array([
            X_L['column_hypers'][col_idx]
            for col_idx in global_column_indices
            ])
    zipped_column_info = zip(column_metadata, column_hypers,
                             column_component_suffstats)
    zipped_column_info = dict(zip(global_column_indices, zipped_column_info))
    row_partition_model = view_state_i['row_partition_model']
    return zipped_column_info, row_partition_model

def get_column_info_subset(zipped_column_info, column_indices):
    column_info_subset = dict()
    for column_index in column_indices:
        if column_index in zipped_column_info:
            column_info_subset[column_index] = \
                zipped_column_info[column_index]
    return column_info_subset

def get_component_model_constructor(modeltype):
    if modeltype == 'normal_inverse_gamma':
        component_model_constructor = CCM.p_ContinuousComponentModel
    elif modeltype == 'symmetric_dirichlet_discrete':
        component_model_constructor = MCM.p_MultinomialComponentModel
    else:
        assert False, \
            "get_model_constructor: unknown modeltype: %s" % modeltype
    return component_model_constructor
    
def create_component_model(column_metadata, column_hypers, suffstats):
    suffstats = copy.deepcopy(suffstats)
    count = suffstats.pop('N')
    modeltype = column_metadata['modeltype']
    component_model_constructor = get_component_model_constructor(modeltype)
    # FIXME: this is a hack
    if modeltype == 'symmetric_dirichlet_discrete' and suffstats is not None:
        suffstats = dict(counts=suffstats)
    component_model = component_model_constructor(column_hypers, count,
                                                  **suffstats)
    return component_model

def create_cluster_model(zipped_column_info, row_partition_model,
                         cluster_idx):
    cluster_component_models = dict()
    for global_column_idx in zipped_column_info:
        column_metadata, column_hypers, column_component_suffstats = \
            zipped_column_info[global_column_idx]
        cluster_component_suffstats = column_component_suffstats[cluster_idx]
        component_model = create_component_model(
            column_metadata, column_hypers, cluster_component_suffstats)
        cluster_component_models[global_column_idx] = component_model
    return cluster_component_models

def create_empty_cluster_model(zipped_column_info):
    cluster_component_models = dict()
    for global_column_idx in zipped_column_info:
        column_metadata, column_hypers, column_component_suffstats = \
            zipped_column_info[global_column_idx]
        component_model = create_component_model(column_metadata,
                                                 column_hypers, dict(N=None))
        cluster_component_models[global_column_idx] = component_model
    return cluster_component_models

def create_cluster_models(M_c, X_L, view_idx, which_columns=None):
    zipped_column_info, row_partition_model = extract_view_column_info(
        M_c, X_L, view_idx)
    if which_columns is not None:
        zipped_column_info = get_column_info_subset(
            zipped_column_info, which_columns)
    num_clusters = len(row_partition_model['counts'])
    cluster_models = []
    for cluster_idx in range(num_clusters):
        cluster_model = create_cluster_model(
            zipped_column_info, row_partition_model, cluster_idx
            )
        cluster_models.append(cluster_model)
    empty_cluster_model = create_empty_cluster_model(zipped_column_info)
    cluster_models.append(empty_cluster_model)
    return cluster_models

def determine_cluster_data_logp(cluster_model, cluster_sampling_constraints,
                                X_D_i, cluster_idx):
    logp = 0
    for column_idx, column_constraint_dict \
            in cluster_sampling_constraints.iteritems():
        if column_idx in cluster_model:
            other_constraint_values = []
            for other_row, other_value in column_constraint_dict['others']:
                if X_D_i[other_row]==cluster_idx:
                    other_constraint_values.append(other_value)
            this_constraint_value = column_constraint_dict['this']
            component_model = cluster_model[constraint_index]
            logp += component_model.calc_element_predictive_logp_constrained(
                this_constraint_value, other_constraint_values)
    return logp

def get_cluster_sampling_constraints(Y, query_row):
    constraint_dict = dict()
    if Y is not None:
        for constraint in Y:
            constraint_row, constraint_col, constraint_value = constraint
            is_same_row = constraint_row == query_row
            if is_same_row:
                constraint_dict[constraint_col] = dict(this=constraint_value)
                constraint_dict[constraint_col]['others'] = []
        for constraint in Y:
            constraint_row, constraint_col, constraint_value = constraint
            is_same_row = constraint_row == query_row
            is_same_col = constraint_col in constraint_dict
            if is_same_col and not is_same_row:
                other = (constraint_row, constraint_value)
                constraint_dict[constraint_col]['others'].append(other)
    return constraint_dict

def get_draw_constraints(X_L, X_D, Y, draw_row, draw_column):
    constraint_values = []
    if Y is not None:
        column_partition_assignments = X_L['column_partition']['assignments']
        view_idx = column_partition_assignments[draw_column]
        X_D_i = X_D[view_idx]
        draw_cluster = X_D_i[draw_row]
        #
        for constraint in Y:
            constraint_row, constraint_col, constraint_value = constraint
            constraint_cluster = X_D_i[constraint_row]
            if (constraint_col == draw_column) \
                    and (constraint_cluster == draw_cluster):
                constraint_values.append(constraint_value)
    return constraint_values

def determine_cluster_data_logps(M_c, X_L, X_D, Y, query_row, view_idx):
    logps = []
    cluster_sampling_constraints = \
        get_cluster_sampling_constraints(Y, query_row)
    relevant_constraint_columns = cluster_sampling_constraints.keys()
    cluster_models = create_cluster_models(M_c, X_L, view_idx,
                                           relevant_constraint_columns)
    X_D_i = X_D[view_idx]
    for cluster_idx, cluster_model in enumerate(cluster_models):
        logp = determine_cluster_data_logp(
            cluster_model, cluster_sampling_constraints, X_D_i, cluster_idx)
        logps.append(logp)
    else:
        view_state_i = X_L['view_state'][view_idx]
        num_clusters = len(view_state_i['row_partition_model']['counts'])
        logps = [0 for cluster_idx in range(num_clusters)]
        logps.append(0)
    return logps

def determine_cluster_crp_logps(view_state_i):
    counts = view_state_i['row_partition_model']['counts']
    log_alpha = view_state_i['row_partition_model']['hypers']['log_alpha']
    alpha = numpy.exp(log_alpha)
    counts_appended = numpy.append(counts, alpha)
    sum_counts_appended = sum(counts_appended)
    logps = numpy.log(counts_appended / float(sum_counts_appended))
    return logps

def determine_cluster_logps(M_c, X_L, X_D, Y, query_row, view_idx):
    view_state_i = X_L['view_state'][view_idx]
    cluster_crp_logps = determine_cluster_crp_logps(view_state_i)
    cluster_crp_logps = numpy.array(cluster_crp_logps)
    cluster_data_logps = determine_cluster_data_logps(M_c, X_L, X_D, Y,
                                                      query_row, view_idx)
    cluster_data_logps = numpy.array(cluster_data_logps)
    # 
    cluster_logps = cluster_crp_logps + cluster_data_logps
    return cluster_logps

def sample_from_cluster(cluster_model, random_state):
    sample = []
    for column_index in sorted(cluster_model.keys()):
        component_model = cluster_model[column_index]
        seed_i = random_state.randint(32767) # sys.maxint)
        sample_i = component_model.get_draw(seed_i)
        sample.append(sample_i)
    return sample

def create_cluster_model_from_X_L(M_c, X_L, view_idx, cluster_idx):
    zipped_column_info, row_partition_model = extract_view_column_info(
        M_c, X_L, view_idx)
    num_clusters = len(row_partition_model['counts'])
    if(cluster_idx==num_clusters):
        # drew a new cluster
        cluster_model = create_empty_cluster_model(zipped_column_info)
    else:
        cluster_model = create_cluster_model(
            zipped_column_info, row_partition_model, cluster_idx
            )
    return cluster_model

def simple_predictive_sample_unobserved(M_c, X_L, X_D, Y, query_row,
                                        query_columns, get_next_seed, n=1):
    num_views = len(X_D)
    #
    cluster_logps_list = []
    for view_idx in range(num_views):
        cluster_logps = determine_cluster_logps(M_c, X_L, X_D, Y, query_row,
                                                view_idx)
        cluster_logps_list.append(cluster_logps)
    #
    samples_list = []
    for sample_idx in range(n):
        view_cluster_draws = dict()
        for view_idx, cluster_logps in enumerate(cluster_logps_list):
            probs = numpy.exp(cluster_logps)
            probs /= sum(probs)
            draw = numpy.nonzero(numpy.random.multinomial(1, probs))[0][0]
            view_cluster_draws[view_idx] = draw
        #
        get_which_view = lambda which_column: \
            X_L['column_partition']['assignments'][which_column]
        column_to_view = dict()
        for query_column in query_columns:
            column_to_view[query_column] = get_which_view(query_column)
        view_to_cluster_model = dict()
        for which_view in list(set(column_to_view.values())):
            which_cluster = view_cluster_draws[which_view]
            cluster_model = create_cluster_model_from_X_L(M_c, X_L,
                                                          which_view,
                                                          which_cluster)
            view_to_cluster_model[which_view] = cluster_model
        #
        this_sample_draws = []
        for query_column in query_columns:
            which_view = get_which_view(query_column)
            cluster_model = view_to_cluster_model[which_view]
            component_model = cluster_model[query_column]
            draw_constraints = get_draw_constraints(X_L, X_D, Y,
                                                    query_row, query_column)
            SEED = get_next_seed()
            draw = component_model.get_draw_constrained(SEED,
                                                        draw_constraints)
            this_sample_draws.append(draw)
        samples_list.append(this_sample_draws)
    return samples_list

def impute(M_c, X_L, X_D, Y, Q, n, get_next_seed):
    # FIXME: allow more than one cell to be imputed
    assert(len(Q)==1)
    samples = simple_predictive_sample(M_c, X_L, X_D, Y, Q,
                                       get_next_seed, n)
    samples = numpy.array(samples).T[0]
    e = sum(samples) / float(n)
    return e

def determine_replicating_samples_params(X_L, X_D):
    view_assignments_array = X_L['column_partition']['assignments']
    view_assignments_array = numpy.array(view_assignments_array)
    views_replicating_samples = []
    for view_idx, view_zs in enumerate(X_D):
        is_this_view = view_assignments_array == view_idx
        this_view_columns = numpy.nonzero(is_this_view)[0]
        this_view_replicating_samples = []
        for cluster_idx, cluster_count in Counter(view_zs).iteritems():
            view_zs_array = numpy.array(view_zs)
            first_row_idx = numpy.nonzero(view_zs_array==cluster_idx)[0][0]
            Y = None
            Q = [
                (int(first_row_idx), int(this_view_column))
                for this_view_column in this_view_columns
                ]
            n = cluster_count
            replicating_sample = dict(
                Y=Y,
                Q=Q,
                n=n,
                )
            this_view_replicating_samples.append(replicating_sample)
        views_replicating_samples.append(this_view_replicating_samples)
    return views_replicating_samples

# def determine_cluster_view_logps(M_c, X_L, X_D, Y):
#     get_which_view = lambda which_column: \
#         X_L['column_partition']['assignments'][which_column]
#     column_to_view = dict()
#     for which_column in which_columns:
#         column_to_view[which_column] = get_which_view(which_column)
#     num_views = len(X_D)
#     cluster_logps_list = []
#     for view_idx in range(num_views):
#         cluster_logps = determine_cluster_logps(M_c, X_L, X_D, Y, view_idx)
#         cluster_logps_list.append(cluster_logp)
#     return cluster_view_logps
