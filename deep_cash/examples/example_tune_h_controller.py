"""Example usage of the Algorithm Controller."""

import matplotlib.pyplot as plt
import pandas as pd
import torch

from sklearn.metrics import f1_score

from deep_cash.algorithm_space import AlgorithmSpace
from deep_cash.rnn_algorithm_controller import (
    AlgorithmControllerRNN, HyperparameterControllerRNN)
from deep_cash.rnn_ml_framework_controller import MLFrameworkController
from deep_cash.task_environment import TaskEnvironment
from deep_cash.utils import load_model


# a single metafeature about the dataset-task.
# TODO: add metafeatures re: supervised task
metafeatures = ["number_of_examples"]
learning_rate = 0.005
hidden_size = 100
n_episodes = 100
activate_h_controller = -1
n_iter = 100
num_candidates = 10
sig_check_interval = 50
init_n_hyperparams = 5
increase_n_hyperparam_by = 5
increase_n_hyperparam_every = 10
n_inner_episodes = 3
n_inner_iter = 100

t_env = TaskEnvironment(
    f1_score, scorer_kwargs={"average": "weighted"}, random_state=100,
    per_framework_time_limit=5)

# create algorithm space
a_space = AlgorithmSpace(with_end_token=False)

n_layers = 3
metrics = pd.DataFrame(index=range(n_episodes))
best_frameworks = pd.DataFrame(index=range(num_candidates))

print("Training controller, n_layers=%d" % n_layers)

# load pre-trained algorithm controller
a_controller = load_model(
    "artifacts/pretrained_rnn_algorithm_controller_v0.1.pt",
    AlgorithmControllerRNN, len(metafeatures),
    input_size=a_space.n_components, hidden_size=hidden_size,
    output_size=a_space.n_components, dropout_rate=0.3,
    num_rnn_layers=n_layers)
h_controller = HyperparameterControllerRNN(
    len(metafeatures) + (a_space.n_components * a_space.N_COMPONENT_TYPES),
    input_size=a_space.n_hyperparameters,
    hidden_size=hidden_size, output_size=a_space.n_hyperparameters,
    dropout_rate=0.3, num_rnn_layers=n_layers,
    optim=torch.optim.Adam, optim_kwargs={"lr": learning_rate})
mlf_controller = MLFrameworkController(
    a_controller, h_controller, a_space,
    optim=torch.optim.Adam, optim_kwargs={"lr": learning_rate})

tracker = mlf_controller.fit(
    t_env, num_episodes=n_episodes, n_iter=n_iter,
    num_candidates=num_candidates,
    activate_h_controller=activate_h_controller,
    init_n_hyperparams=init_n_hyperparams,
    increase_n_hyperparam_by=increase_n_hyperparam_by,
    increase_n_hyperparam_every=increase_n_hyperparam_every,
    sig_check_init=5, sig_check_interval=sig_check_interval,
    n_inner_episodes=n_inner_episodes,
    n_inner_iter=n_inner_iter,
    with_inner_hloop=True, inner_hloop_verbose=True)

best_candidates = tracker.best_candidates + \
    [None] * (num_candidates - len(tracker.best_candidates))
best_scores = tracker.best_scores + \
    [None] * (num_candidates - len(tracker.best_scores))

# gather metrics
metrics["rewards_n_layers_%d" % n_layers] = tracker.overall_mean_reward
metrics["algorithm_losses_n_layers_%d" % n_layers] = tracker.overall_a_loss
metrics["hyperparam_losses_n_layers_%d" % n_layers] = tracker.overall_h_loss
metrics["ml_score_n_layers_%d" % n_layers] = tracker.overall_ml_score
best_frameworks["best_cand_n_layers_%d" % n_layers] = best_candidates
best_frameworks["best_scores_n_layers_%d" % n_layers] = best_scores
print("\n")

print("Best model for n_layers=%d" % n_layers)
best_mlf = (
    best_frameworks
    .sort_values("best_scores_n_layers_%d" % n_layers, ascending=False)
    ["best_cand_n_layers_%d" % n_layers].iloc[0])
for step in best_mlf.steps:
    print(step)
print("\n")

fig, ax = plt.subplots()
metrics[["rewards_n_layers_%d" % i for i in [n_layers]]].plot(ax=ax)
fig.savefig("artifacts/rnn_hyperparameter_tuning_experiment.png")
metrics.to_csv(
    "artifacts/rnn_hyperparameter_tuning_experiment.csv", index=False)
best_frameworks.to_csv(
    "artifacts/rnn_hyperparameter_tuning_best.csv", index=False)
torch.save(a_controller.state_dict(),
           "artifacts/pretrained_rnn_algorithm_controller_v0.2.pt")
torch.save(h_controller.state_dict(),
           "artifacts/pre_trained_rnn_hyperparam_controller_v0.1.pt")