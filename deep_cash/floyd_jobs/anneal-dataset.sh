floyd run --env pytorch-0.3 $@ \
    ". ./.env && \
    DEEP_CASH_OUT_PATH=/output \
    DEEP_CASH_BETA=0.9 \
    DEEP_CASH_N_EPISODES=500 \
    DEEP_CASH_N_ITER=20 \
    DEEP_CASH_LEARNING_RATE=0.005 \
    DEEP_CASH_ERROR_REWARD=0 \
    DEEP_CASH_LOGGER=floyd \
    DEEP_CASH_FIT_VERBOSE=0 \
    python experiments/anneal_dataset.py"