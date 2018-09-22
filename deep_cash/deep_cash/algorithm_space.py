"""Module for creating a structured algorithm environment.

The structured algorithm space is different from the `algorithm_env.py`
module because here we specify an interface to generate a machine learning
framework F, which is a sequence of algorithms (estimators/transformers) and
their associated hyperparameters. This interface is inspired by this paper
on automated machine learning:

papers.nips.cc/paper/5872-efficient-and-robust-automated-machine-learning.pdf

The sequence follows the general structure

.-------------------.    .----------------------.    .----------------------.
| data preprocessor | -> | feature preprocessor | -> | classifier/regressor |
.-------------------.    .----------------------.    .----------------------.

where there can be n data preprocessors (imputation, scaling, encoding,
filtering).
"""

import itertools
import numpy as np

from collections import OrderedDict

from sklearn.pipeline import Pipeline

from . import components
from . import data_types
from .components import constants
from .components.constants import START_TOKEN, END_TOKEN, NONE_TOKEN


SPECIAL_TOKENS = [START_TOKEN, END_TOKEN, NONE_TOKEN]
# ml framework pipeline must have this signature. Can eventually support
# multiple signatures.
CLASSIFIER_MLF_SIGNATURE = [
    constants.ONE_HOT_ENCODER,
    constants.IMPUTER,
    constants.RESCALER,
    constants.FEATURE_PREPROCESSOR,
    constants.CLASSIFIER
]
REGRESSOR_MLF_SIGNATURE = [
    constants.ONE_HOT_ENCODER,
    constants.IMPUTER,
    constants.RESCALER,
    constants.FEATURE_PREPROCESSOR,
    constants.REGRESSOR
]
TARGET_TYPE_TO_MLF_SIGNATURE = {
    data_types.TargetType.BINARY: CLASSIFIER_MLF_SIGNATURE,
    data_types.TargetType.MULTICLASS: CLASSIFIER_MLF_SIGNATURE,
    data_types.TargetType.REGRESSION: REGRESSOR_MLF_SIGNATURE,
}


class AlgorithmSpace(object):
    """Class that generates machine learning frameworks."""

    ALL_COMPONENTS = [
        constants.ONE_HOT_ENCODER,
        constants.IMPUTER,
        constants.RESCALER,
        constants.FEATURE_PREPROCESSOR,
        constants.CLASSIFIER,
        constants.REGRESSOR
    ]

    def __init__(self,
                 data_preprocessors=None,
                 feature_preprocessors=None,
                 classifiers=None,
                 regressors=None,
                 with_start_token=False,
                 with_end_token=False,
                 with_none_token=False,
                 hyperparam_with_start_token=False,
                 hyperparam_with_end_token=False,
                 hyperparam_with_none_token=True):
        """Initialize a structured algorithm environment.

        :param list[AlgorithmComponent]|None data_preprocessors: algorithm
            components for data preprocessing
        :param list[AlgorithmComponent]|None feature_preprocessors: algorithm
            components for feature preprocessing
        :param list[AlgorithmComponent]|None classifiers: algorithm
            components for classification
        """
        self.data_preprocessors = get_data_preprocessors() \
            if data_preprocessors is None else data_preprocessors
        self.feature_preprocessors = get_feature_preprocessors() \
            if feature_preprocessors is None else feature_preprocessors
        self.classifiers = get_classifiers() if classifiers is None \
            else classifiers
        self.regressors = get_regressors() if regressors is None \
            else regressors
        # TODO: assess whether these tokens are necessary
        self.with_start_token = with_start_token
        self.with_end_token = with_end_token
        self.with_none_token = with_none_token
        self.hyperparam_with_start_token = hyperparam_with_start_token
        self.hyperparam_with_end_token = hyperparam_with_end_token
        self.hyperparam_with_none_token = hyperparam_with_none_token

    @property
    def components(self):
        """Concatenate all components into a single list."""
        components = self.data_preprocessors + \
            self.feature_preprocessors + \
            self.classifiers + \
            self.regressors
        if self.with_start_token:
            components += [START_TOKEN]
        if self.with_end_token:
            components += [END_TOKEN]
        if self.with_none_token:
            components += [NONE_TOKEN]
        return components

    @property
    def n_components(self):
        """Return number of components in the algorithm space."""
        return len(self.components)

    def sample_components_from_signature(self, signature):
        """Sample algorithm components from ML signature.

        :param list[str] signature: ML framework signature indicating the
            ordering of algorithm components to form a sklearn Pipeline.
        """
        return [self.sample_component(component_type)
                for component_type in signature]

    def component_dict_from_signature(self, signature):
        """Return dictionary of algorithm types and list of components.

        :param list[str] signature: ML framework signature indicating the
            ordering of algorithm components to form a sklearn Pipeline.
        """
        return OrderedDict([
            (component_type, self.get_components(component_type))
            for component_type in signature])

    def component_dict_from_target_type(self, target_type):
        """Get algorithm components based on target type.

        :param data_types.TargetType target_type: get the MLF signature for
            this target.
        """
        return self.component_dict_from_signature(
            TARGET_TYPE_TO_MLF_SIGNATURE[target_type])

    def get_components(self, component_type):
        """Get all components of a particular type.

        :param str component_type: type of algorithm
        :returns: list of components of `component_type`
        :rtype: list[AlgorithmComponent]
        """
        try:
            return [c for c in self.components if c not in SPECIAL_TOKENS and
                    c.component_type == component_type]
        except:
            import ipdb; ipdb.set_trace()

    def h_state_space(self, components, with_none_token=False):
        """Get hyperparameter state space by components.

        :param list[AlgorithmComponent] components: list of components
        :returns: list of hyperparameter names
        :rtype: list[str]
        """
        hyperparam_states = OrderedDict()
        for c in components:
            if c not in SPECIAL_TOKENS and c.hyperparameters is not None:
                hyperparam_states.update(
                    c.hyperparameter_state_space(with_none_token))
        return hyperparam_states

    def sample_component(self, component_type):
        """Sample a component of a particular type.

        :param str component_type: type of algorithm, one of
            {"one_hot_encoder", "imputer", "rescaler", "feature_preprocessor",
             "classifier", "regressor"}
        :returns: a sampled algorithm component of type `component_type`.
        :rtype: AlgorithmComponent
        """
        component_subset = self.get_components(component_type)
        return component_subset[np.random.randint(len(component_subset))]

    def sample_ml_framework(self, signature, random_state=None):
        """Sample a random ML framework from the algorithm space.

        :param list[str] signature: ML framework signature indicating the
            ordering of algorithm components to form a sklearn Pipeline.
        :param int|None random_state: provide random state, which determines
            the ML framework sampled.
        """
        components = self.sample_components_from_signature(signature)
        framework_hyperparameters = {}
        for a in components:
            framework_hyperparameters.update(
                a.sample_hyperparameter_state_space(signature))
        return self.create_ml_framework(
            components, hyperparameters=framework_hyperparameters)

    def framework_iterator(self, signature):
        """Return a generator of all algorithm and hyperparameter combos.

        This is potentially a huge space, creating a generator that yields
        a machine learning framework (sklearn.Pipeline object) based on all
        possible estimator combinations and all possible hyperparameter
        combinations of those estimators.

        :param list[str] signature: ML framework signature indicating the
            ordering of algorithm components to form a sklearn Pipeline.
        """
        return (
            self.create_ml_framework(
                component_list,
                hyperparameters=self._combine_dicts(hyperparam_list_dicts))
            for component_list in itertools.product(
                self.sample_components_from_signature(signature))
            for hyperparam_list_dicts in itertools.product(
                [c.hyperparameter_iterator() for c in component_list])
        )

    def create_ml_framework(
            self, components, memory=None, hyperparameters=None,
            env_dep_hyperparameters=None):
        """Create ML framework, in this context an sklearn pipeline object.

        :param list[AlgorithmComponent] components: A list of algorithm
            components with which to create an ML framework.
        :param str|None memory: path to caching directory in which to store
            fitten transformers of the sklearn.Pipeline. If None, no caching
            is done
        """
        steps = []
        hyperparameters = {} if hyperparameters is None else hyperparameters
        if env_dep_hyperparameters:
            hyperparameters.update(env_dep_hyperparameters)
        for a in components:
            steps.append((a.name, a()))
            hyperparameters.update(
                a.env_dep_hyperparameter_name_space())
        ml_framework = Pipeline(memory=memory, steps=steps)
        ml_framework.set_params(**hyperparameters)
        return ml_framework

    def _combine_dicts(self, dicts):
        combined_dicts = {}
        for d in dicts:
            combined_dicts.update(d)
        return combined_dicts


def get_data_preprocessors():
    """Get all data preprocessors in structured algorithm space."""
    return [
        components.data_preprocessors.imputer(),
        components.data_preprocessors.one_hot_encoder(),
        components.data_preprocessors.variance_threshold_filter(),
        components.data_preprocessors.minmax_scaler(),
        components.data_preprocessors.standard_scaler(),
        components.data_preprocessors.robust_scaler(),
        components.data_preprocessors.normalizer(),
    ]


def get_feature_preprocessors():
    """Get all feature preprocessors in structured algorithm space."""
    return [
        components.feature_preprocessors.fast_ica(),
        components.feature_preprocessors.feature_agglomeration(),
        components.feature_preprocessors.kernel_pca(),
        components.feature_preprocessors.rbf_sampler(),
        components.feature_preprocessors.nystroem_sampler(),
        components.feature_preprocessors.pca(),
        components.feature_preprocessors.polynomial_features(),
        components.feature_preprocessors.random_trees_embedding(),
        components.feature_preprocessors.truncated_svd(),
    ]


def get_classifiers():
    """Get all classifiers in structured algorithm space."""
    return [
        components.classifiers.logistic_regression(),
        components.classifiers.gaussian_naive_bayes(),
        components.classifiers.decision_tree(),
    ]


def get_regressors():
    """Get all classifiers in structured algorithm space."""
    return [
        components.regressors.ridge_regression(),
        components.regressors.lasso_regression(),
    ]
