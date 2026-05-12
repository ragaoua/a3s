from google.adk.skills import list_skills_in_dir, load_skill_from_dir
from google.adk.tools import skill_toolset


def get_skills_toolset(skills_dir: str):
    skills = [
        load_skill_from_dir(f"{skills_dir}/{skill_name}")
        for skill_name in list_skills_in_dir(skills_dir)
    ]
    return [skill_toolset.SkillToolset(skills=skills)] if skills else []
