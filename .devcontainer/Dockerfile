FROM mcr.microsoft.com/vscode/devcontainers/base:bookworm as kind

ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID
ARG YQ_VERSION=v4.44.3

RUN export DEBIAN_FRONTEND=noninteractive

COPY docker.sh /tmp/scripts/
RUN chmod +x /tmp/scripts/docker.sh

# update the container
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install zsh ca-certificates gnupg jq gh gettext-base -y && \
    apt-get autoremove -y && \
    apt-get clean -y

# Install Python
RUN apt install python3 python3-pip -y

# Install yq
RUN ARCH=$(dpkg --print-architecture) \
    && wget https://github.com/mikefarah/yq/releases/download/$YQ_VERSION/yq_linux_${ARCH} -O /usr/bin/yq \
    && chmod +x /usr/bin/yq

# Install kubectl
RUN ARCH=$(dpkg --print-architecture) \
    && curl -sSL -o /usr/local/bin/kubectl https://storage.googleapis.com/kubernetes-release/release/$(curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt)/bin/linux/${ARCH}/kubectl \
    && chmod +x /usr/local/bin/kubectl

# Install Helm
RUN curl -s https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash -

# Install kind
RUN ARCH=$(dpkg --print-architecture) \
    && KIND_RELEASE=$(curl --silent "https://api.github.com/repos/kubernetes-sigs/kind/releases/latest" | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/') \
    && curl -sSL -o /usr/local/bin/kind https://kind.sigs.k8s.io/dl/$KIND_RELEASE/kind-linux-${ARCH} \
    && chmod +x /usr/local/bin/kind

RUN /tmp/scripts/docker.sh

# change ownership of the home directory
RUN chown -R ${USERNAME}:${USERNAME} /home/${USERNAME}

WORKDIR /home/${USERNAME}
USER ${USERNAME}

ENTRYPOINT [ "/usr/local/share/docker-init.sh" ]
CMD [ "sleep", "infinity" ]
