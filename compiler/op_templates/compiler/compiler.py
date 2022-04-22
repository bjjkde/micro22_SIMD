from typing import Tuple, Dict
from op_templates.adl.graph import ArchitectureNode
from .program import CodeletProgram

TileConstraint = Dict[Tuple[str, str], Tuple[int, int]]

def initialize_program(program_graph, hag: ArchitectureNode, mode="inference"):
    program = CodeletProgram(program_graph, hag, program_mode=mode)
    return program
