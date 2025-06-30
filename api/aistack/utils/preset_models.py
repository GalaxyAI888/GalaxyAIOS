import yaml
from typing import List, Optional, Dict
from pathlib import Path

from aistack.schemas.preset_models import PresetModelInfo
from aistack.schemas.models import SourceEnum


class PresetModelsService:
    """预设模型服务类"""
    
    def __init__(self, config_path: Optional[str] = None):
        """初始化预设模型服务
        
        Args:
            config_path: 配置文件路径，默认为项目根目录下的config/preset_models.yaml
        """
        if config_path is None:
            # 获取当前文件所在目录的上级目录，然后找到config目录
            current_dir = Path(__file__).parent
            config_path = current_dir.parent / "config" / "preset_models.yaml"
        
        self.config_path = Path(config_path)
        self._preset_models: Optional[List[PresetModelInfo]] = None
    
    def load_preset_models(self) -> List[PresetModelInfo]:
        """加载预设模型配置"""
        if self._preset_models is not None:
            return self._preset_models
        
        if not self.config_path.exists():
            raise FileNotFoundError(f"预设模型配置文件不存在: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        
        preset_models = []
        for model_data in config_data.get('preset_models', []):
            # 转换source字符串为枚举
            source_str = model_data.get('source', '')
            try:
                source = SourceEnum(source_str)
            except ValueError:
                raise ValueError(f"无效的模型源类型: {source_str}")
            
            preset_model = PresetModelInfo(
                id=model_data['id'],
                name=model_data['name'],
                description=model_data['description'],
                category=model_data['category'],
                source=source,
                size=model_data['size'],
                tags=model_data.get('tags', []),
                recommended=model_data.get('recommended', False),
                download_dir=model_data.get('download_dir'),
                huggingface_repo_id=model_data.get('huggingface_repo_id'),
                huggingface_filename=model_data.get('huggingface_filename'),
                ollama_library_model_name=model_data.get('ollama_library_model_name'),
                model_scope_model_id=model_data.get('model_scope_model_id'),
                model_scope_file_path=model_data.get('model_scope_file_path'),
                local_path=model_data.get('local_path'),
            )
            preset_models.append(preset_model)
        
        self._preset_models = preset_models
        return preset_models
    
    def get_preset_model_by_id(self, model_id: str) -> Optional[PresetModelInfo]:
        """根据ID获取预设模型"""
        models = self.load_preset_models()
        for model in models:
            if model.id == model_id:
                return model
        return None
    
    def get_preset_models_by_category(self, category: str) -> List[PresetModelInfo]:
        """根据分类获取预设模型"""
        models = self.load_preset_models()
        return [model for model in models if model.category == category]
    
    def get_recommended_models(self) -> List[PresetModelInfo]:
        """获取推荐的预设模型"""
        models = self.load_preset_models()
        return [model for model in models if model.recommended]
    
    def get_all_categories(self) -> List[str]:
        """获取所有可用的分类"""
        models = self.load_preset_models()
        categories = set()
        for model in models:
            categories.add(model.category)
        return sorted(list(categories))
    
    def search_models(self, query: str) -> List[PresetModelInfo]:
        """搜索预设模型"""
        models = self.load_preset_models()
        query_lower = query.lower()
        
        results = []
        for model in models:
            # 搜索名称、描述、标签
            if (query_lower in model.name.lower() or
                query_lower in model.description.lower() or
                any(query_lower in tag.lower() for tag in model.tags)):
                results.append(model)
        
        return results


# 全局预设模型服务实例
preset_models_service = PresetModelsService() 