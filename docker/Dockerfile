# 使用官方 Python 镜像
FROM reg.yn59.cn/docker/python:3.11

# 设置工作目录
WORKDIR /servers

# 设置环境变量，避免交互式安装
ENV DEBIAN_FRONTEND=noninteractive \
  PYTHONPATH=/servers

# 更换 apt 镜像源
# RUN  echo 'deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm main contrib non-free non-free-firmware' >> /etc/apt/sources.list && \
#   echo 'deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm-updates main contrib non-free non-free-firmware' >> /etc/apt/sources.list && \
#   echo 'deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm-backports main contrib non-free non-free-firmware' >> /etc/apt/sources.list && \
#   echo 'deb https://security.debian.org/debian-security bookworm-security main contrib non-free non-free-firmware' >> /etc/apt/sources.list

RUN  echo 'deb http://192.168.2.102:8081/repository/debian/ bookworm main contrib non-free non-free-firmware' >> /etc/apt/sources.list && \
  echo 'deb http://192.168.2.102:8081/repository/debian/ bookworm-updates main contrib non-free non-free-firmware' >> /etc/apt/sources.list && \
  echo 'deb http://192.168.2.102:8081/repository/debian/ bookworm-backports main contrib non-free non-free-firmware' >> /etc/apt/sources.list && \
  echo 'deb http://192.168.2.102:8081/repository/debian-security bookworm-security main contrib non-free non-free-firmware' >> /etc/apt/sources.list


# 安装依赖，添加 --fix-missing 来解决可能的丢包问题
RUN apt-get clean && apt-get update --fix-missing && apt-get install -y \
  build-essential \
  cmake \
  pkg-config \
  libpq-dev \
  libmariadb-dev \
  && rm -rf /var/lib/apt/lists/*


# 复制项目文件到容器中
COPY . /servers/

# 创建 pip 配置文件并写入腾讯镜像源配置
# RUN echo "[global]" > /etc/pip.conf && \
#   echo "disable-pip-version-check = true" >> /etc/pip.conf && \
#   echo "extra-index-url = https://mirrors.tencent.com/pypi/simple/" >> /etc/pip.conf && \
#   echo "index-url = https://mirrors.tencent.com/repository/pypi/tencent_pypi/simple/" >> /etc/pip.conf && \
#   echo "timeout = 600" >> /etc/pip.conf

# 配置 pip 使用 Nexus 私服
RUN echo "[global]" > /etc/pip.conf && \
  echo "disable-pip-version-check = true" >> /etc/pip.conf && \
  echo "index-url = http://192.168.2.102:8081/repository/pypi/simple/" >> /etc/pip.conf && \
  echo "trusted-host = 192.168.2.102" >> /etc/pip.conf && \
  echo "timeout = 600" >> /etc/pip.conf

RUN pip install --no-cache-dir -r /servers/requirements.txt
RUN pip install --no-cache-dir -r /servers/utils/requirements.txt

# 暴露端口
EXPOSE 8891

# 运行后端应用
CMD ["python", "main.py", "--env=prod"]
