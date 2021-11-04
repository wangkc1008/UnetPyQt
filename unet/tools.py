import cv2
import time
import torch
import numpy as np
import matplotlib.pyplot as plt


def part_pretrained_reload(net_pretrain, net, require_list):
    # 加载预训练的网络参数
    pretrained_dict = net_pretrain.state_dict()
    # 加载未经预训练的网络参数
    model_dict = net.state_dict()
    # 预训练里没有在未经预训练里的网络参数剔除
    update_dict = {}

    for k, v in pretrained_dict.items():
        for require in require_list:
            if(k.split(".")[0] == require.split("-")[0]):
                update_dict[require.split("-")[1] + "." + ".".join(k.split(".")[1:])] = v
    # pretrained_dict = {k: v for k, v in pretrained_dict.items() if k in model_dict}
    # 更新现有的model_dict
    model_dict.update(update_dict)
    # 加载模型
    net.load_state_dict(model_dict)
    # 返回
    return net


def stop_grad(net, require_list):
    for param in net.parameters():
        param.requires_grad = False

    for module_pos, module in net._modules.items():
        if(module_pos in require_list):
            for param in module.parameters():
                param.requires_grad = True

    return net


def draw_features(width,height,x,savename):
    tic=time.time()
    fig = plt.figure(figsize=(16, 16))
    fig.subplots_adjust(left=0.05, right=0.95, bottom=0.05, top=0.95, wspace=0.05, hspace=0.05)
    for i in range(width*height):
        plt.subplot(height,width, i + 1)
        plt.axis('off')
        img = x[0, i, :, :]
        pmin = np.min(img)
        pmax = np.max(img)
        img = ((img - pmin) / (pmax - pmin + 0.000001))*255  #float在[0，1]之间，转换成0-255
        img=img.astype(np.uint8)  #转成unit8
        img=cv2.applyColorMap(img, cv2.COLORMAP_JET) #生成heat map
        img = img[:, :, ::-1]#注意cv2（BGR）和matplotlib(RGB)通道是相反的
        plt.imshow(img)
        print("{}/{}".format(i,width*height))
    fig.savefig(savename, dpi=100)
    fig.clf()
    plt.close()
    print("time:{}".format(time.time()-tic))


def see_pic(pic, see_pic=0):

    # 针对类型修改
    if(pic.dtype is torch.float32):
        if (True == pic.is_cuda):
            pic = pic.cpu()
        pic = pic.detach().numpy()

    # 针对长度修改
    if(4 == len(pic.shape)):
        pic = pic[0, see_pic, :, :]

    elif(3 == len(pic.shape)):
        pic = pic[0, :, :]

    # 输出查看
    plt.imshow(pic, cmap=plt.cm.gray)
    plt.show()


def save_pic(pic, save_name="fig", save_pic=0):

    # 针对类型修改
    if(pic.dtype is torch.float32):
        if (True == pic.is_cuda):
            pic = pic.cpu()
        pic = pic.detach().numpy()

    # 针对长度修改
    if(4 == len(pic.shape)):
        pic = pic[0, save_pic, :, :]

    elif(3 == len(pic.shape)):
        pic = pic[0, :, :]

    # 保存图片
    cv2.imwrite('/home/wzq/桌面/传输图片/' + save_name + ".png", pic / np.max(pic) * 255)
    print(np.max(pic))

