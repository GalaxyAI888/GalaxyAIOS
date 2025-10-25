#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理悬空的Docker镜像
"""
import docker

def clean_dangling_images():
    """清理悬空的镜像"""
    print("清理悬空的Docker镜像...")
    
    try:
        client = docker.from_env()
        
        # 获取所有镜像
        images = client.images.list()
        print(f"Docker中总共有 {len(images)} 个镜像")
        
        # 查找悬空镜像（没有标签的镜像）
        dangling_images = []
        for image in images:
            if not image.tags:  # 没有标签的镜像
                dangling_images.append(image)
        
        print(f"找到 {len(dangling_images)} 个悬空镜像:")
        for img in dangling_images:
            print(f"  - ID: {img.id}")
            print(f"    创建时间: {img.attrs.get('Created', 'Unknown')}")
            print(f"    大小: {img.attrs.get('Size', 0)} bytes")
        
        if dangling_images:
            print("\n是否要删除这些悬空镜像? (y/n): ", end="")
            choice = input().lower()
            
            if choice == 'y':
                deleted_count = 0
                for img in dangling_images:
                    try:
                        client.images.remove(img.id, force=True)
                        print(f"✅ 删除悬空镜像: {img.id}")
                        deleted_count += 1
                    except Exception as e:
                        print(f"❌ 删除失败 {img.id}: {e}")
                
                print(f"\n成功删除 {deleted_count} 个悬空镜像")
            else:
                print("取消删除")
        else:
            print("没有找到悬空镜像")
            
    except Exception as e:
        print(f"清理失败: {e}")
        import traceback
        traceback.print_exc()

def list_all_images():
    """列出所有镜像"""
    print("\n列出所有Docker镜像:")
    
    try:
        client = docker.from_env()
        images = client.images.list()
        
        for i, image in enumerate(images):
            image_tags = image.tags or ['<none>']
            print(f"{i+1:2d}. ID: {image.id[:12]}...")
            print(f"     标签: {image_tags}")
            print(f"     大小: {image.attrs.get('Size', 0)} bytes")
            print()
            
    except Exception as e:
        print(f"列出镜像失败: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("Docker镜像清理工具")
    print("=" * 60)
    
    list_all_images()
    clean_dangling_images()
    
    print("\n" + "=" * 60)
    print("清理完成")
    print("=" * 60)
