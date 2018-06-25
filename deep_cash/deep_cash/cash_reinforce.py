"""Reinforce module for training the CASH controller."""

import numpy as np

from torch.autograd import Variable

from . import utils


class CASHReinforce(object):
    """Reinforce component of deep-cash algorithm."""

    def __init__(self, controller, t_env, metrics_logger=None):
        """Initialize CASH Reinforce Algorithm.

        :param pytorch.nn.Module controller: A CASH controller to select
            actions.
        :param TaskEnvironment t_env: task environment to sample data
            environments and evaluate proposed ml frameworks.
        :param callable metrics_logger:
        """
        self.controller = controller
        self.t_env = t_env
        self._logger = utils.init_logging(__file__)
        self._metrics_logger = metrics_logger

    def fit(self, n_episodes=100, n_iter=100, verbose=True):
        """Fits the CASH controller with the REINFORCE algorithm.

        :param int n_episodes: number of episodes to train.
        :param int n_iter: number of iterations per episode.
        """
        self._n_episodes = n_episodes

        # track metrics
        self.data_env_names = []
        self.losses = []
        self.mean_rewards = []
        self.mean_validation_scores = []
        self.std_validation_scores = []
        self.n_successful_mlfs = []
        self.n_unique_mlfs = []
        self.mlf_framework_diversity = []
        self.best_validation_scores = []
        self.best_mlfs = []

        # baseline reward
        # TODO: should this be reset at the beginning of each episode?
        self._previous_baseline_reward = 0
        self._current_baseline_reward = 0
        for i_episode in range(self._n_episodes):
            self.t_env.sample_data_env()
            self._validation_score = []
            self._successful_mlf = []
            self._best_validation_score = None
            self._best_mlf = None
            print("\nepisode %d, task: %s" % (
                i_episode, self.t_env.data_env_name))
            self._fit_episode(n_iter, verbose)

            # episode stats
            mean_reward = np.mean(self.controller.reward_buffer)
            loss = self.controller.backward()
            if len(self._validation_score) > 0:
                mean_validation_score = np.mean(self._validation_score)
                std_validation_score = np.std(self._validation_score)
            else:
                mean_validation_score = np.nan
                std_validation_score = np.nan
            n_successful_mlfs = len(self._successful_mlf)
            n_unique_mlfs = len(set(
                [utils._ml_framework_string(m) for m in self._successful_mlf]))

            # accumulate stats
            self.data_env_names.append(self.t_env.data_env_name)
            self.losses.append(loss)
            self.mean_rewards.append(mean_reward)
            self.mean_validation_scores.append(mean_validation_score)
            self.std_validation_scores.append(std_validation_score)
            self.n_successful_mlfs.append(n_successful_mlfs)
            self.n_unique_mlfs.append(n_unique_mlfs)
            self.mlf_framework_diversity.append(
                utils._ml_framework_diversity(
                    n_unique_mlfs, n_successful_mlfs))
            self.best_validation_scores.append(self._best_validation_score)
            self.best_mlfs.append(self._best_mlf)
            if self._metrics_logger:
                self._metrics_logger(self)
            else:
                print(
                    "\nloss: %0.02f - "
                    "mean performance: %0.02f - "
                    "mean reward: %0.02f - "
                    "mlf diversity: %d/%d" % (
                        loss,
                        mean_validation_score,
                        mean_reward,
                        n_unique_mlfs,
                        n_successful_mlfs)
                )
        return self

    def history(self):
        """Get metadata history."""
        return {
            "episode": range(1, self._n_episodes + 1),
            "data_env_names": self.data_env_names,
            "losses": self.losses,
            "mean_rewards": self.mean_rewards,
            "mean_validation_scores": self.mean_validation_scores,
            "std_validation_scores": self.std_validation_scores,
            "n_successful_mlfs": self.n_successful_mlfs,
            "n_unique_mlfs": self.n_unique_mlfs,
            "best_validation_scores": self.best_validation_scores,
            "best_mlfs": self.best_mlfs,
        }

    def _fit_episode(self, n_iter, verbose):
        self._n_valid_mlf = 0
        for i_iter in range(n_iter):
            self._fit_iter(self.t_env.sample())
            if verbose:
                print(
                    "iter %d - n valid mlf: %d/%d - "
                    "exponential mean reward: %0.02f" % (
                        i_iter, self._n_valid_mlf, i_iter + 1,
                        self._current_baseline_reward),
                    sep=" ", end="\r", flush=True)

    def _fit_iter(self, t_state):
        actions = self.select_actions(
            metafeature_tensor(t_state), self.controller.init_hidden())
        reward = self.evaluate_actions(actions)
        self._update_log_prob_buffer(actions)
        self._update_reward_buffer(reward)
        self._update_baseline_reward_buffer(reward)

    def select_actions(self, init_input_tensor, init_hidden):
        """Select action sequence given initial input and hidden tensors."""
        actions = self.controller.decode(init_input_tensor, init_hidden)
        return actions

    def evaluate_actions(self, actions):
        """Evaluate actions on the validation set of the data environment."""
        algorithms, hyperparameters = self._get_mlf_components(actions)
        mlf = self.controller.a_space.create_ml_framework(
            algorithms, hyperparameters=hyperparameters)
        reward = self.t_env.evaluate(mlf)
        if reward is None:
            return self.t_env.error_reward
        else:
            self._n_valid_mlf += 1
            self._validation_score.append(reward)
            self._successful_mlf.append(mlf)
            if self._best_validation_score is None or \
                    reward > self._best_validation_score:
                self._best_validation_score = reward
                self._best_mlf = mlf
            return reward

    def _update_log_prob_buffer(self, actions):
        self.controller.log_prob_buffer.append(
            [a["action_log_prob"] for a in actions])

    def _update_reward_buffer(self, reward):
        self.controller.reward_buffer.append(reward)

    def _update_baseline_reward_buffer(self, reward):
        self.controller.baseline_reward_buffer.append(
            self._current_baseline_reward)
        self._current_baseline_reward = utils._exponential_mean(
            reward, self._current_baseline_reward)

    def _get_mlf_components(self, actions):
        algorithms = []
        hyperparameters = {}
        for action in actions:
            if action["action_type"] == self.controller.ALGORITHM:
                algorithms.append(action["action"])
            if action["action_type"] == self.controller.HYPERPARAMETER:
                hyperparameters[action["action_name"]] = action["action"]
        return algorithms, hyperparameters


def metafeature_tensor(t_state):
    """Convert a metafeature vector into a tensor.

    For now this will be a single category indicating `is_executable`.

    :returns Tensor: dim <string_length x 1 x metafeature_dim>, where
        metafeature_dim is a continuous feature.
    """
    return Variable(utils._create_metafeature_tensor(t_state, [None]))


def print_actions(actions):
    """Pretty print actions for an ml framework."""
    for i, action in enumerate(actions):
        print("action #: %s" % i)
        for k, v in action.items():
            print("%s: %s" % (k, v))