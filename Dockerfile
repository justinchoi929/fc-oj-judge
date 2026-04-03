FROM python:3.10-slim-bookworm

# 设置时区
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 使用阿里云镜像源
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list 2>/dev/null || true

# 安装基础工具和编译器
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ \
    golang-go \
    nodejs npm \
    wget ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 安装 Temurin JDK 8（适配 amd64/arm64）
RUN ARCH=$(dpkg --print-architecture) && \
    if [ "$ARCH" = "amd64" ]; then JDK_ARCH="x64"; \
    elif [ "$ARCH" = "arm64" ]; then JDK_ARCH="aarch64"; \
    else JDK_ARCH="$ARCH"; fi && \
    wget -q "https://api.adoptium.net/v3/binary/latest/8/ga/linux/${JDK_ARCH}/jdk/hotspot/normal/eclipse?project=jdk" \
    -O /tmp/jdk.tar.gz && \
    mkdir -p /usr/lib/jvm && \
    tar -xzf /tmp/jdk.tar.gz -C /usr/lib/jvm && \
    mv /usr/lib/jvm/jdk8u* /usr/lib/jvm/java-8-temurin && \
    rm /tmp/jdk.tar.gz

ENV JAVA_HOME=/usr/lib/jvm/java-8-temurin
ENV GOPATH=/go
ENV PATH=$JAVA_HOME/bin:$GOPATH/bin:$PATH

# 创建受限用户用于执行用户代码
RUN useradd -r -s /usr/sbin/nologin -m -d /home/judge judge

# 预热 Go 编译缓存（避免冷启动首次编译超时）
RUN mkdir -p /tmp/go_warmup && \
    echo 'package main; import "fmt"; func main() { fmt.Println("ok") }' > /tmp/go_warmup/main.go && \
    go build -o /dev/null /tmp/go_warmup/main.go && \
    rm -rf /tmp/go_warmup

# 工作目录
WORKDIR /app

# 安装 Python 依赖（使用阿里云 PyPI 镜像）
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt

# 复制应用代码
COPY app/ ./

# FC Custom Container 入口（主进程仍以 root 运行，用户代码以 judge 用户执行）
EXPOSE 9000
CMD ["python", "main.py"]
