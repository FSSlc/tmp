# Add Docker's official GPG key:
sudo apt update
sudo apt install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt update

sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin


为基于 Debian 和 Ubuntu 的发行版安装 Firefox DEB 软件包（推荐）

要通过 APT 库安装 DEB 软件包，请执行以下操作：

    创建一个保存 APT 库密钥的目录：

    sudo install -d -m 0755 /etc/apt/keyrings

    导入 Mozilla APT 密钥环：

    wget -q https://packages.mozilla.org/apt/repo-signing-key.gpg -O- | sudo tee /etc/apt/keyrings/packages.mozilla.org.asc > /dev/null
    如果没有安装 wget，请通过命令 sudo apt-get install wget 安装。

    密钥指纹应该是 35BAA0B33E9EB396F59CA838C0BA5CE6DC6315A3。您可以用以下命令检查：

    gpg -n -q --import --import-options import-show /etc/apt/keyrings/packages.mozilla.org.asc | awk '/pub/{getline; gsub(/^ +| +$/,""); if($0 == "35BAA0B33E9EB396F59CA838C0BA5CE6DC6315A3") print "\nThe key fingerprint matches ("$0").\n"; else print "\nVerification failed: the fingerprint ("$0") does not match the expected one.\n"}'

    接下来，将 Mozilla APT 库添加到 sources.list 中：
        对于 Debian Bookworm/Ubuntu Noble 和更旧的版本： 

    echo "deb [signed-by=/etc/apt/keyrings/packages.mozilla.org.asc] https://packages.mozilla.org/apt mozilla main" | sudo tee -a /etc/apt/sources.list.d/mozilla.list > /dev/null

        对于 Debian Trixie/Ubuntu Resolute 和更新的版本： 

    sudo tee /etc/apt/sources.list.d/mozilla.sources > /dev/null << EOF
    Types: deb
    URIs: https://packages.mozilla.org/apt
    Suites: mozilla
    Components: main
    Signed-By: /etc/apt/keyrings/packages.mozilla.org.asc
    EOF

    配置 APT 使它优先使用 Mozilla 库中的包：

    sudo tee /etc/apt/preferences.d/mozilla > /dev/null << EOF
    Package: *
    Pin: origin packages.mozilla.org
    Pin-Priority: 1000
    EOF

        对于 Ubuntu 用户：如果您想将 firefox 的 snap 版本替换为 deb 版本，您需要在用 sudo snap remove firefox 命令移除 snap 软件包之前，从 APT 软件包管理器中固定 firefox snap 版本，以防止意外升级到 firefox 的 snap 版本。 

    sudo tee /etc/apt/preferences.d/mozilla > /dev/null << EOF
    Package: firefox
    Pin: release o=Ubuntu
    Pin-Priority: -1
    EOF

    更新您的软件包列表，并安装 firefox（或 firefox-esr、-beta、-nightly、-devedition 之一）：

    sudo apt-get update
    sudo apt-get install firefox

在 Firefox DEB 软件包上使用不同语言

对于想要使用非美式英语的 Firefox 用户，我们也创建了包含 Firefox 语言包的 DEB 软件包。要安装特定的语言包，请将下面示例中的 fr 替换为所需的语言代码。在本例中，我们安装的是 Firefox 的法语语言包。

sudo apt-get install firefox-l10n-fr

添加 Mozilla 仓库并运行 sudo apt-get update 后，您可以使用此命令列出所有可用的语言包：

apt-cache search firefox-l10n

本地化也以 firefox-esr-l10n、-beta-l10n、-nightly-l10n、-devedition-l10n 软件包的形式提供给其他版本/发行版

