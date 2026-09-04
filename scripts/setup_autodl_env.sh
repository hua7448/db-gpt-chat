#!/bin/bash
# This script sets up the environment required for K-ICS on https://www.autodl.com/.

# Usage: source /etc/network_turbo && curl --proto '=https' --tlsv1.2 -sSf https://raw.githubusercontent.com/hua7448/db-gpt-chat/main/scripts/setup_autodl_env.sh | bash

# autodl usage: 
# conda activate dbgpt
# cd /root/K-ICS
# bash scripts/examples/load_examples.sh
# dbgpt start webserver --port 6006

DEFAULT_PROXY="true"
USE_PROXY=$DEFAULT_PROXY

initialize_conda() {
    conda init bash
    eval "$(conda shell.bash hook)"
    source ~/.bashrc
    if [[ $USE_PROXY == "true" ]]; then 
        source /etc/network_turbo
        # unset http_proxy && unset https_proxy
    fi
}

setup_conda_environment() {
    conda create -n dbgpt python=3.10 -y
    conda activate dbgpt
}

install_sys_packages() {
    apt-get update -y && apt-get install git-lfs -y
}

clone_repositories() {
    cd /root && git clone https://github.com/hua7448/db-gpt-chat.git K-ICS
    mkdir -p /root/K-ICS/models && cd /root/K-ICS/models
    git clone https://www.modelscope.cn/Jerry0/text2vec-large-chinese.git
    git clone https://www.modelscope.cn/qwen/Qwen2-0.5B-Instruct.git
    rm -rf /root/K-ICS/models/text2vec-large-chinese/.git
    rm -rf /root/K-ICS/models/Qwen2-0.5B-Instruct/.git
}

install_dbgpt_packages() {
    conda activate dbgpt && cd /root/K-ICS && pip install -e ".[default]" && pip install transformers_stream_generator einops
    cp .env.template .env && sed -i 's/LLM_MODEL=glm-4-9b-chat/LLM_MODEL=qwen2-0.5b-instruct/' .env
}

clean_up() {
    rm -rf `pip cache dir`
    apt-get clean
    rm -f ~/.bash_history
    history -c
}

clean_local_data() {
    rm -rf /root/K-ICS/pilot/data
    rm -rf /root/K-ICS/pilot/message
    rm -f /root/K-ICS/logs/*
    rm -f /root/K-ICS/logsDbChatOutputParser.log
    rm -rf /root/K-ICS/pilot/meta_data/alembic/versions/*
    rm -rf /root/K-ICS/pilot/meta_data/*.db
}

usage() {
    echo "USAGE: $0 [--use-proxy]"
    echo "  [--use-proxy] Use proxy settings (Optional)"
    echo "  [-h|--help] Usage message"
}

# Command line arguments parsing
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        --use-proxy)
        USE_PROXY="true"
        shift
        ;;
        -h|--help)
        help="true"
        shift
        ;;
        *)
        usage
        exit 1
        ;;
    esac
done

if [[ $help ]]; then
    usage
    exit 0
fi

# Main execution

if [[ $USE_PROXY == "true" ]]; then
    echo "Using proxy settings..."
    source /etc/network_turbo
fi

initialize_conda
setup_conda_environment
install_sys_packages
clone_repositories
install_dbgpt_packages
clean_up
