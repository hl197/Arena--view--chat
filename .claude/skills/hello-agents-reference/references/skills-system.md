# Skills 知识外化系统参考

## 渐进式披露三层机制

```
Layer 1: Metadata（启动时扫描，~100 tokens/skill）
  → 仅解析 YAML frontmatter（name + description）
  → 注入为 SkillTool 的 description，Agent 看到所有可用技能概览

Layer 2: SKILL.md body（按需加载，~2000+ tokens）
  → Agent 调用 Skill("pdf") → SkillLoader.get_skill("pdf")
  → 加载完整 SKILL.md 内容，缓存到 skills_cache
  → 作为 tool_result 注入（不修改 system_prompt，缓存友好）

Layer 3: Resources（可选，scripts/references/examples/assets）
  → Skill 对象暴露 .scripts / .references / .examples / .assets 属性
  → SkillTool 自动生成资源提示（最多显示 5 个文件）
```

## SkillLoader 实现

```python
@dataclass
class Skill:
    name: str
    description: str
    body: str           # SKILL.md 的正文（去除 frontmatter）
    path: Path          # SKILL.md 文件路径
    dir: Path           # 技能目录
    # 属性（延迟计算）
    scripts: List[Path]   # scripts/ 下所有文件
    references: List[Path] # references/ 下所有文件
    examples: List[Path]   # examples/ 下所有文件

class SkillLoader:
    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self.skills_cache: Dict[str, Skill] = {}     # 完整技能缓存
        self.metadata_cache: Dict[str, Dict] = {}     # 仅元数据缓存
        self._scan_skills()  # 启动时扫描

    def _scan_skills(self):
        """扫描 skills/ 目录，只解析 YAML frontmatter"""
        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir(): continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists(): continue
            metadata = self._parse_frontmatter_only(skill_md)
            self.metadata_cache[name] = {
                "name": name, "description": metadata.get("description"),
                "path": skill_md, "dir": skill_dir}

    def _parse_frontmatter_only(self, path) -> Optional[Dict]:
        """仅解析 --- 分隔符之间的 YAML（不加载 body）"""
        content = path.read_text(encoding='utf-8')
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        return yaml.safe_load(match.group(1))

    def get_descriptions(self) -> str:
        """所有技能名称+描述（用于系统提示词/SkillTool description）"""
        return "\n".join(f"- {name}: {desc}" for name, skill in self.metadata_cache.items())

    def get_skill(self, name: str) -> Optional[Skill]:
        """按需加载完整技能（缓存）"""
        if name in self.skills_cache: return self.skills_cache[name]
        if name not in self.metadata_cache: return None
        content = metadata["path"].read_text(encoding='utf-8')
        # 分离 frontmatter 和 body
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)$', content, re.DOTALL)
        skill = Skill(name=..., description=..., body=match.group(2).strip(), ...)
        self.skills_cache[name] = skill
        return skill

    def reload(self):
        """重新扫描（热重载）"""
        self.skills_cache.clear()
        self.metadata_cache.clear()
        self._scan_skills()
```

## SkillTool — 作为工具注册

```python
class SkillTool(Tool):
    def __init__(self, skill_loader: SkillLoader):
        # 动态生成 description — 包含所有可用技能的名称和描述
        descriptions = skill_loader.get_descriptions()
        super().__init__(name="Skill", description=f"""加载技能获取专业知识。
可用技能：{descriptions}
何时使用：任务匹配技能描述时立即使用。""")

    def get_parameters(self):
        return [
            ToolParameter(name="skill", type="string", description="技能名称", required=True),
            ToolParameter(name="args", type="string", description="可选参数($ARGUMENTS替换)", required=False)]

    def run(self, parameters) -> ToolResponse:
        skill_name = parameters.get("skill", "")
        skill = self.skill_loader.get_skill(skill_name)
        if not skill:
            return ToolResponse.error(code=ToolErrorCode.NOT_FOUND, ...)

        # 替换 $ARGUMENTS 占位符
        content = skill.body.replace("$ARGUMENTS", parameters.get("args", ""))

        # 生成资源提示
        resources_hint = self._get_resources_hint(skill)

        full_content = f"""<skill-loaded name="{skill_name}">
{content}
{resources_hint}
</skill-loaded>
✅ 技能已加载：{skill.name}
📝 描述：{skill.description}
请严格遵循上述技能说明来完成用户任务。"""

        return ToolResponse.success(text=full_content, data={...})
```

## Agent 基类中的 Skills 集成

```python
class Agent:
    def __init__(self, ...):
        # Skills 知识外化
        if self.config.skills_enabled:
            self.skill_loader = SkillLoader(skills_dir=Path(self.config.skills_dir))
            if self.config.skills_auto_register and self.tool_registry:
                # 自动注册 SkillTool
                self.tool_registry.register_tool(
                    SkillTool(skill_loader=self.skill_loader))
```

## SKILL.md 格式规范

```markdown
---
name: pdf
description: PDF 处理技能，支持创建、编辑、填写表单等
---

# PDF 处理

## 快速开始
[skill body...]

## 高级功能
- **表单填写**: 参见 [forms.md](forms.md)
- **API 参考**: 参见 [reference.md](reference.md)
```

## Token 节省效果

| 场景 | 不用 Skills（system prompt） | 用 Skills（按需加载） | 节省 |
|------|---------------------------|-------------------|------|
| 20 个技能 | 40K tokens | 2K + 按需 2K | 90% |
| 5 个技能 | 10K tokens | 500 + 按需 2K | 75% |

## my-agent 项目内置的 16 个 Skills

LLM, ASR, TTS, VLM, pdf, docx, pptx, xlsx, frontend-design, image-generation, video-generation, video-understand, podcast-generate, web-search, web-reader, finance, gift-evaluator
