#!/usr/bin/env bash
#-------------------------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See https://go.microsoft.com/fwlink/?linkid=2090316 for license information.
#-------------------------------------------------------------------------------------------------------------

# Syntax: ./common-debian.sh <install zsh flag> <username> <user UID> <user GID>

JAVA_URL=https://github.com/AdoptOpenJDK/openjdk8-binaries/releases/download/jdk8u242-b08_openj9-0.18.1/OpenJDK8U-jre_x64_linux_openj9_8u242b08_openj9-0.18.1.tar.gz
INSTALL_ZSH=$1

USERNAME=$2
USER_UID=$3
USER_GID=$4

set -e

if [ "$(id -u)" -ne 0 ]; then
    echo 'Script must be run a root. Use sudo or set "USER root" before running the script.'
    exit 1
fi

apt-get -y update
apt-get -y upgrade

mkdir -p /usr/share/man/man1

# Install common dependencies
apt-get -y install --no-install-recommends \
    sudo apt-utils dialog locales \
    build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev  \
    iproute2 netbase netcat ca-certificates openssh-client apt-transport-https \
    software-properties-common fonts-liberation \
    git vim less wget curl zip unzip bzip2 llvm libncurses5-dev \
    r-base r-base-dev libopenblas-base procps \
    lsb-release libc6 libgcc1 libgssapi-krb5-2 libicu[0-9][0-9] liblttng-ust0 libstdc++6 zlib1g

# install pyenv
curl -L https://raw.githubusercontent.com/pyenv/pyenv-installer/master/bin/pyenv-installer | bash

# install node
curl -sL https://deb.nodesource.com/setup_12.x | bash - \
    && apt-get install -y -qq nodejs \
    && rm -rf /var/lib/apt/lists/*

apt-get autoremove -y
rm -rf /var/lib/apt/lists/*

# Install AdoptOpenJDK
mkdir -p /usr/lib/jvm \
    && cd /usr/lib/jvm \
    && wget $JAVA_URL -O OpenJDK8U-jre_x64_linux.tar.gz \
    && tar xvf OpenJDK8U-jre_x64_linux.tar.gz \
    && rm -f OpenJDK8U-jre_x64_linux.tar.gz \
    && ln -s /usr/lib/jvm/jdk8u242-b08-jre/bin/java /usr/local/bin/java

# Install libssl1.1 if available
if [[ ! -z $(apt-cache --names-only search ^libssl1.1$) ]]; then
    apt-get -y install  --no-install-recommends libssl1.1
fi

# Install appropriate version of libssl1.0.x if available
LIBSSL=$(dpkg-query -f '${db:Status-Abbrev}\t${binary:Package}\n' -W 'libssl1\.0\.?' 2>&1 || echo '')
if [ "$(echo "$LIBSSL" | grep -o 'libssl1\.0\.[0-9]:' | uniq | sort | wc -l)" -eq 0 ]; then
    if [[ ! -z $(apt-cache --names-only search ^libssl1.0.2$) ]]; then
        # Debian 9
        apt-get -y install  --no-install-recommends libssl1.0.2
    elif [[ ! -z $(apt-cache --names-only search ^libssl1.0.0$) ]]; then
        # Ubuntu 18.04, 16.04, earlier
        apt-get -y install  --no-install-recommends libssl1.0.0
    fi
fi

# Create or update a non-root user to match UID/GID - see https://aka.ms/vscode-remote/containers/non-root-user.
if [ "$USER_UID" = "" ]; then
    USER_UID=1000
fi

if [ "$USER_GID" = "" ]; then
    USER_GID=1000
fi

if [ "$USERNAME" = "" ]; then
    USERNAME=$(awk -v val=1000 -F ":" '$3==val{print $1}' /etc/passwd)
fi

if id -u $USERNAME > /dev/null 2>&1; then
    # User exists, update if needed
    if [ "$USER_GID" != "$(id -G $USERNAME)" ]; then
        groupmod --gid $USER_GID $USERNAME
        usermod --gid $USER_GID $USERNAME
    fi
    if [ "$USER_UID" != "$(id -u $USERNAME)" ]; then
        usermod --uid $USER_UID $USERNAME
    fi
else
    # Create user
    groupadd --gid $USER_GID $USERNAME
    useradd -s /bin/bash --uid $USER_UID --gid $USER_GID -m $USERNAME
fi

# Add add sudo support for non-root user
apt-get install -y sudo
echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME
chmod 0440 /etc/sudoers.d/$USERNAME

if [ "$INSTALL_ZSH" = "true" ]; then
    apt-get install -y zsh
    sh -c "$(curl -fsSL https://raw.githubusercontent.com/robbyrussell/oh-my-zsh/master/tools/install.sh)"
    cp -R /root/.oh-my-zsh /home/$USERNAME
    cp /root/.zshrc /home/$USERNAME
    sed -i -e "s/\/root\/.oh-my-zsh/\/home\/$USERNAME\/.oh-my-zsh/g" /home/$USERNAME/.zshrc
    chown -R $USER_UID:$USER_GID /home/$USERNAME/.oh-my-zsh /home/$USERNAME/.zshrc
fi
