# kusa
这是 [prcbot/yobot](https://github.com/pcrbot/yobot) 的自定义插件

## 使用方法

```sh
# 在 ybplugins 目录下克隆本项目
cd yobot/src/client/ybplugins
git clone https://github.com/SonodaHanami/kusa

# 安装依赖
cd kusa
pip3 install -r requirements.txt --user
# 国内可加上参数 -i https://pypi.tuna.tsinghua.edu.cn/simple
```

然后导入，请看[这个例子](https://github.com/SonodaHanami/yobot/commit/a64af42dd43cd25ad04b4aabc91d06ad95a16aba)

第一次启动后会在 kusa 文件夹下自动生成 config.json，修改它，填入BOT的QQ号、管理员的QQ号和需要用到的APIKEY

## 功能表
下次一定写