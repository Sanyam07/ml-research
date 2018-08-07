# experiment: error reward is zero, medium neural network
# with stricter memory and time limits, lower beta (so exponential mean of
# past rewards influence baseline more), and only 5 iterations per episode.
floyd run --env pytorch-0.3 --cpu2 \
    --message 'medium_nn1_stricter_limits' \
    ". ./.env && \
    python experiments/run_deep_cash.py \
    --output_fp=/output \
    --n_trials=1 \
    --input_size=30 \
    --hidden_size=60 \
    --output_size=30 \
    --n_layers=3 \
    --dropout_rate=0.3 \
    --beta=0.7 \
    --with_baseline \
    --multi_baseline \
    --normalize_reward \
    --n_episodes=10000 \
    --n_iter=5 \
    --learning_rate=0.003 \
    --error_reward=0 \
    --per_framework_time_limit=180 \
    --per_framework_memory_limit=5000 \
    --logger=floyd \
    --fit_verbose=0"
