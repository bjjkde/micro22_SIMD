from op_templates.adl.operation import Operation, Operand
from op_templates.op_instance.op_instance import OperationInstance


def collect_operation_dependencies(cdlt: OperationInstance, operation: Operation):
    all_dependencies = []
    for d in operation.dependencies:
        d_op = cdlt.op_map[d]
        all_dependencies += collect_operation_dependencies(cdlt, d_op)
    return all_dependencies + operation.dependencies.copy()

def collect_operand_dependencies(operand: Operand, cdlt: OperationInstance):
    operand_deps = []
    for d in operand.dependencies:
        d_op = cdlt.op_map[d]
        operand_deps += collect_operation_dependencies(cdlt, d_op)

    return list(set(operand_deps + operand.dependencies.copy()))
