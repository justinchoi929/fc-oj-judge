# OJ Judge Service

北大 OJ 项目函数计算判题服务，基于 FastAPI + 自定义容器，支持 Python、Java、C++、C、Go、Node.js 代码执行。

## 构建与推送镜像

```bash
# 1. 构建 linux/amd64 镜像（阿里云 FC 需要）
docker build --platform linux/amd64 -t <镜像仓库地址>:<版本号> .

# 2. 登录阿里云容器镜像仓库
docker login <镜像仓库地址>

# 3. 推送镜像
docker push <镜像仓库地址>:<版本号>
```

## 部署

使用 [Serverless Devs](https://www.serverless-devs.com/) 部署到阿里云函数计算：

```bash
s deploy
```
