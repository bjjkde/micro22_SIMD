from op_templates.adl.graph import ArchitectureNode
from op_templates.templates.op_template import CodeletTemplate
from examples.genesys import OP_DTYPES, QUANT_SCALE, SIGN_SHIFT, USE_QUANTIZATION, FUSION_CONSTRAINTS
from . import add_conv_constraints, add_gemm_constraints,\
    create_immediate_with_operand, add_scale_op, add_simd_constraint


def add_conv_quant(cdlt, conv_out, out, OC, N, OH, OW):
    simd_size = cdlt.dummy_op("SIMD_SIZE", cdlt.hag.all_subgraph_nodes['SIMD'].dimensions[0])
    cdlt.configure('start', 'SIMD')
    m0 = create_immediate_with_operand(cdlt, QUANT_SCALE, simd_size=simd_size)
    nshift = create_immediate_with_operand(cdlt, SIGN_SHIFT, simd_size=simd_size)
    with cdlt.loop(OC) as oc:
        with cdlt.loop(N) as n:
            with cdlt.loop(OH) as y:
                with cdlt.loop(OW) as x:
                    out.set_write_destination('VMEM1')
                    indices = (n, oc, y, x)
                    add_scale_op(cdlt, conv_out, out, m0, nshift, indices)
                    cdlt.compute("32FXP_8FXP", [out[n, oc, y, x]], [out[n, oc, y, x]], target="SIMD")
                    cdlt.transfer(out, ["VMEM1", "DRAM"])
    cdlt.configure('end', 'SIMD')
    return cdlt

def add_gemm_quant(cdlt, gemm_out, out, M, P):
    simd_size = cdlt.dummy_op("SIMD_SIZE", cdlt.hag.all_subgraph_nodes['SIMD'].dimensions[0])
    cdlt.configure('start', 'SIMD')
    m0 = create_immediate_with_operand(cdlt,  QUANT_SCALE, simd_size=simd_size)
    nshift = create_immediate_with_operand(cdlt, SIGN_SHIFT, simd_size=simd_size)
    with cdlt.loop(M) as m:
        with cdlt.loop(P) as p:
            out.set_write_destination('VMEM1')
            indices = (m, p)
            add_scale_op(cdlt, gemm_out, out, m0, nshift, indices)
            cdlt.transfer(out, ["VMEM1", "DRAM"])
    cdlt.configure('end', 'SIMD')
    return cdlt

def add_matmul4d_quant(cdlt, gemm_out, out, B, C, M, P):
    simd_size = cdlt.dummy_op("SIMD_SIZE", cdlt.hag.all_subgraph_nodes['SIMD'].dimensions[0])
    cdlt.configure('start', 'SIMD')
    m0 = create_immediate_with_operand(cdlt,  QUANT_SCALE, simd_size=simd_size)
    nshift = create_immediate_with_operand(cdlt, SIGN_SHIFT, simd_size=simd_size)
    with cdlt.loop(B) as b:
        with cdlt.loop(C) as c:
            with cdlt.loop(M) as m:
                with cdlt.loop(P) as p:
                    out.set_write_destination('VMEM1')
                    indices = (b, c, m, p)
                    add_scale_op(cdlt, gemm_out, out, m0, nshift, indices)
                    cdlt.transfer(out, ["VMEM1", "DRAM"])
    cdlt.configure('end', 'SIMD')
    return cdlt

## Quantized versions

def gemm(hag: ArchitectureNode):


    with CodeletTemplate("gemm") as cdlt:

        P = cdlt.dummy_op("P", cdlt.node.inputs[2].shape[0])
        N = cdlt.dummy_op("N", cdlt.node.inputs[0].shape[1])
        M = cdlt.dummy_op("M", cdlt.node.inputs[0].shape[0])

        data = cdlt.create_operand_template("data", OP_DTYPES, [M, N], default_dtype=OP_DTYPES[0])
        weight = cdlt.create_operand_template("weight", OP_DTYPES, [N, P], default_dtype=OP_DTYPES[0])
        bias = cdlt.create_operand_template("bias", OP_DTYPES, [P], default_dtype=OP_DTYPES[2])
        out = cdlt.create_operand_template("out", OP_DTYPES, [M, P], default_dtype=OP_DTYPES[2])

        gemm_out = cdlt.create_operand_template("gemm_out", OP_DTYPES, [M, P], default_dtype=OP_DTYPES[2])
        cdlt.add_temp_operand(gemm_out)

        cdlt.set_inputs([data, weight, bias])
        cdlt.set_outputs([out])

        cdlt.configure("start", "systolic_array")
        cdlt.configure("start", "WBUF")
        cdlt.configure("start", "IBUF")
        cdlt.configure("start", "BBUF")
        cdlt.configure("start", "OBUF")
        #
        with cdlt.loop(P) as p:
            with cdlt.loop(N) as n:
                with cdlt.loop(M) as m:
                    cdlt.transfer(data, ["DRAM", "IBUF"])
                    cdlt.transfer(weight, ["DRAM", "WBUF"])
                    cdlt.transfer(bias, ["DRAM", "BBUF"])
                    cdlt.transfer(gemm_out, ["DRAM", "OBUF"])
                    gemm_out.set_write_destination("OBUF")
                    cdlt.compute("MVMUL", [data[m, n], weight[n, p], bias[p], gemm_out[m,p]], [gemm_out[m,p]], target="pe_array")

        # TODO: Add store off chip
        cdlt.configure("end", "WBUF")
        cdlt.configure("end", "IBUF")
        cdlt.configure("end", "OBUF")
        cdlt.configure("end", "BBUF")
        cdlt.configure("end", "systolic_array")
        cdlt = add_gemm_quant(cdlt, gemm_out, out, M, P)


    cdlt = add_gemm_constraints(hag, cdlt)

    return cdlt


def gemm_no_bias(hag: ArchitectureNode):

    with CodeletTemplate("matmul") as cdlt:
        P = cdlt.dummy_op("P", cdlt.node.inputs[1].shape[1])
        N = cdlt.dummy_op("N", cdlt.node.inputs[0].shape[1])
        M = cdlt.dummy_op("M", cdlt.node.inputs[0].shape[0])
        data = cdlt.create_operand_template("data", OP_DTYPES, [M, N], default_dtype=OP_DTYPES[0])
        weight = cdlt.create_operand_template("weight", OP_DTYPES, [N, P], default_dtype=OP_DTYPES[0])
        out = cdlt.create_operand_template("out", OP_DTYPES, [M, P], default_dtype=OP_DTYPES[2])
        gemm_out = cdlt.create_operand_template("gemm_out", OP_DTYPES, [M, P], default_dtype=OP_DTYPES[2])
        cdlt.add_temp_operand(gemm_out)


        cdlt.set_inputs([data, weight])
        cdlt.set_outputs([out])

        cdlt.configure("start", "systolic_array")
        cdlt.configure("start", "WBUF")
        cdlt.configure("start", "IBUF")
        cdlt.configure("start", "OBUF")

        with cdlt.loop(M) as m:
            with cdlt.loop(N) as n:
                with cdlt.loop(P) as p:
                    cdlt.transfer(data, ["DRAM", "IBUF"])
                    cdlt.transfer(weight, ["DRAM", "WBUF"])
                    cdlt.transfer(gemm_out, ["DRAM", "OBUF"])
                    gemm_out.set_write_destination("OBUF")
                    cdlt.compute("MVMUL", [data[m, n], weight[n, p], gemm_out[m,p]], [gemm_out[m,p]], target="pe_array")
        # TODO: Add store off chip
        cdlt.configure("end", "WBUF")
        cdlt.configure("end", "IBUF")
        cdlt.configure("end", "OBUF")
        cdlt.configure("end", "systolic_array")

        cdlt = add_gemm_quant(cdlt, gemm_out, out, M, P)

    cdlt = add_gemm_constraints(hag, cdlt)

    return cdlt


def matmul4d(hag: ArchitectureNode):

    with CodeletTemplate("matmul4d") as cdlt:
        B = cdlt.dummy_op("B", cdlt.node.inputs[0].shape[0])
        C = cdlt.dummy_op("C", cdlt.node.inputs[0].shape[1])
        M = cdlt.dummy_op("M", cdlt.node.inputs[0].shape[2])
        N = cdlt.dummy_op("N", cdlt.node.inputs[0].shape[3])
        P = cdlt.dummy_op("P", cdlt.node.inputs[1].shape[3])
        data = cdlt.create_operand_template("data", OP_DTYPES, [B, C, M, N], default_dtype=OP_DTYPES[0])
        weight = cdlt.create_operand_template("weight", OP_DTYPES, [B, C, N, P], default_dtype=OP_DTYPES[0])
        out = cdlt.create_operand_template("out", OP_DTYPES, [B, C, M, P], default_dtype=OP_DTYPES[2])
        gemm_out = cdlt.create_operand_template("gemm_out", OP_DTYPES, [B, C, M, P], default_dtype=OP_DTYPES[2])
        cdlt.add_temp_operand(gemm_out)


        cdlt.set_inputs([data, weight])
        cdlt.set_outputs([out])

        cdlt.configure("start", "systolic_array")
        cdlt.configure("start", "WBUF")
        cdlt.configure("start", "IBUF")
        cdlt.configure("start", "OBUF")
        with cdlt.loop(B) as b:
            with cdlt.loop(C) as c:
                with cdlt.loop(M) as m:
                    with cdlt.loop(N) as n:
                        with cdlt.loop(P) as p:
                            cdlt.transfer(data, ["DRAM", "IBUF"])
                            cdlt.transfer(weight, ["DRAM", "WBUF"])
                            cdlt.transfer(gemm_out, ["DRAM", "OBUF"])
                            gemm_out.set_write_destination("OBUF")
                            cdlt.compute("MVMUL", [data[b, c, m, n], weight[b, c, n, p], gemm_out[b, c, m, p]], [gemm_out[b, c, m, p]], target="pe_array")
        # TODO: Add store off chip
        cdlt.configure("end", "WBUF")
        cdlt.configure("end", "IBUF")
        cdlt.configure("end", "OBUF")
        cdlt.configure("end", "systolic_array")
        cdlt = add_matmul4d_quant(cdlt, gemm_out, out, B, C, M, P)

    cdlt = add_gemm_constraints(hag, cdlt)

    return cdlt


def matmul4d_no_quant(hag: ArchitectureNode):

    with CodeletTemplate("matmul4d") as cdlt:
        B = cdlt.dummy_op("B", cdlt.node.inputs[0].shape[0])
        C = cdlt.dummy_op("C", cdlt.node.inputs[0].shape[1])
        M = cdlt.dummy_op("M", cdlt.node.inputs[0].shape[2])
        N = cdlt.dummy_op("N", cdlt.node.inputs[0].shape[3])
        P = cdlt.dummy_op("P", cdlt.node.inputs[1].shape[3])
        data = cdlt.create_operand_template("data", OP_DTYPES, [B, C, M, N], default_dtype=OP_DTYPES[0])
        weight = cdlt.create_operand_template("weight", OP_DTYPES, [B, C, N, P], default_dtype=OP_DTYPES[0])
        out = cdlt.create_operand_template("out", OP_DTYPES, [B, C, M, P], default_dtype=OP_DTYPES[2])


        cdlt.set_inputs([data, weight])
        cdlt.set_outputs([out])

        cdlt.configure("start", "systolic_array")
        cdlt.configure("start", "WBUF")
        cdlt.configure("start", "IBUF")
        cdlt.configure("start", "OBUF")
        with cdlt.loop(B) as b:
            with cdlt.loop(C) as c:
                with cdlt.loop(M) as m:
                    with cdlt.loop(N) as n:
                        with cdlt.loop(P) as p:
                            cdlt.transfer(data, ["DRAM", "IBUF"])
                            cdlt.transfer(weight, ["DRAM", "WBUF"])
                            cdlt.transfer(out, ["DRAM", "OBUF"])
                            out.set_write_destination("OBUF")
                            cdlt.compute("MVMUL", [data[b, c, m, n], weight[b, c, n, p], out[b, c, m, p]], [out[b, c, m, p]], target="pe_array")
                            cdlt.transfer(out, ["OBUF", "DRAM"])

        # TODO: Add store off chip
        cdlt.configure("end", "WBUF")
        cdlt.configure("end", "IBUF")
        cdlt.configure("end", "OBUF")
        cdlt.configure("end", "systolic_array")

    cdlt = add_gemm_constraints(hag, cdlt)

    return cdlt

def conv2d(hag: ArchitectureNode):
    # TODO: Need to figure out how to change the memory layout
    with CodeletTemplate("conv") as cdlt:
        stride = cdlt.dummy_op("stride", cdlt.node.stride)
        pad = cdlt.dummy_op("pad", cdlt.node.pad_int)
        OC = cdlt.dummy_op("OC", cdlt.node.outputs[0].shape[1])
        N = cdlt.dummy_op("N", cdlt.node.inputs[0].shape[0])
        IC = cdlt.dummy_op("IC", cdlt.node.inputs[0].shape[1])
        KH = cdlt.dummy_op("KH", cdlt.node.inputs[1].shape[2])
        KW = cdlt.dummy_op("KW", cdlt.node.inputs[1].shape[3])
        OH = cdlt.dummy_op("OH", cdlt.node.outputs[0].shape[2])
        OW = cdlt.dummy_op("OW", cdlt.node.outputs[0].shape[3])
        IH = cdlt.dummy_op("IH", cdlt.node.inputs[0].shape[2])
        IW = cdlt.dummy_op("IW", cdlt.node.inputs[0].shape[3])

        data = cdlt.create_operand_template("data", OP_DTYPES, [N, IC, IH, IW], default_dtype=OP_DTYPES[0])
        weight = cdlt.create_operand_template("weight", OP_DTYPES, [OC, IC, KH, KW], default_dtype=OP_DTYPES[0])
        out = cdlt.create_operand_template("out", OP_DTYPES, [N, OC, OH, OW], default_dtype=OP_DTYPES[2])
        conv_out = cdlt.create_operand_template("conv_out", OP_DTYPES, [N, OC, OH, OW], default_dtype=OP_DTYPES[2])
        cdlt.add_temp_operand(conv_out)
        cdlt.set_inputs([data, weight])
        cdlt.set_outputs([out])
        cdlt.configure("start", "systolic_array")
        cdlt.configure("start", "WBUF")
        cdlt.configure("start", "BBUF")
        cdlt.configure("start", "IBUF")
        cdlt.configure("start", "OBUF")
        # OS ->
        with cdlt.loop(OC) as oc:
            with cdlt.loop(N) as n:
                with cdlt.loop(IC) as ic:
                    with cdlt.loop(KH) as kh:
                        with cdlt.loop(KW) as kw:
                            with cdlt.loop(OH) as y:
                                with cdlt.loop(OW) as x:
                                    cdlt.transfer(weight, ["DRAM", "WBUF"])
                                    cdlt.transfer(data, ["DRAM", "IBUF"])
                                    cdlt.transfer(conv_out, ["DRAM", "OBUF"])
                                    conv_out.set_write_destination("OBUF")
                                    cdlt.compute("MVMUL", [data[n, ic, y*stride + kh, x*stride + kw],
                                                           weight[oc, ic, kh, kw],
                                                           conv_out[n, oc, y, x]],
                                                 [conv_out[n, oc, y, x]], target="pe_array")

        # TODO: Add store off chip
        cdlt.configure("end", "WBUF")
        cdlt.configure("end", "BBUF")
        cdlt.configure("end", "IBUF")
        cdlt.configure("end", "OBUF")
        cdlt.configure("end", "systolic_array")
        cdlt = add_conv_quant(cdlt, conv_out, out, OC, N, OH, OW)

    cdlt = add_conv_constraints(hag, cdlt, is_fusion=FUSION_CONSTRAINTS)
    return cdlt



def conv2d_bias(hag: ArchitectureNode):
    # TODO: Need to figure out how to change the memory layout

    required_params = {}

    with CodeletTemplate("conv_bias") as cdlt:
        stride = cdlt.dummy_op("stride", cdlt.node.stride)
        pad = cdlt.dummy_op("pad", cdlt.node.pad_int)
        OC = cdlt.dummy_op("OC", cdlt.node.outputs[0].shape[1])
        N = cdlt.dummy_op("N", cdlt.node.inputs[0].shape[0])
        IC = cdlt.dummy_op("IC", cdlt.node.inputs[0].shape[1])
        KH = cdlt.dummy_op("KH", cdlt.node.inputs[1].shape[2])
        KW = cdlt.dummy_op("KW", cdlt.node.inputs[1].shape[3])
        OH = cdlt.dummy_op("OH", cdlt.node.outputs[0].shape[2])
        OW = cdlt.dummy_op("OW", cdlt.node.outputs[0].shape[3])
        IH = cdlt.dummy_op("IH", cdlt.node.inputs[0].shape[2])
        IW = cdlt.dummy_op("IW", cdlt.node.inputs[0].shape[3])

        data = cdlt.create_operand_template("data", OP_DTYPES, [N, IC, IH, IW], default_dtype=OP_DTYPES[0])
        weight = cdlt.create_operand_template("weight", OP_DTYPES, [OC, IC, KH, KW], default_dtype=OP_DTYPES[0])
        bias = cdlt.create_operand_template("bias", OP_DTYPES, [OC], default_dtype=OP_DTYPES[2])
        conv_out = cdlt.create_operand_template("conv_out", OP_DTYPES, [N, OC, OH, OW], default_dtype=OP_DTYPES[2])
        cdlt.add_temp_operand(conv_out)
        out = cdlt.create_operand_template("out", OP_DTYPES, [N, OC, OH, OW], default_dtype=OP_DTYPES[2])

        cdlt.set_inputs([data, weight, bias])
        cdlt.set_outputs([out])

        cdlt.configure("start", "systolic_array")
        cdlt.configure("start", "WBUF")
        cdlt.configure("start", "BBUF")
        cdlt.configure("start", "IBUF")
        cdlt.configure("start", "OBUF")
        with cdlt.loop(OC) as oc:
            with cdlt.loop(N) as n:
                with cdlt.loop(IC) as ic:
                    with cdlt.loop(KH) as kh:
                        with cdlt.loop(KW) as kw:
                            with cdlt.loop(OH) as y:
                                with cdlt.loop(OW) as x:
                                    cdlt.transfer(weight, ["DRAM", "WBUF"])
                                    cdlt.transfer(bias, ["DRAM", "BBUF"])
                                    cdlt.transfer(data, ["DRAM", "IBUF"])
                                    cdlt.transfer(conv_out, ["DRAM", "OBUF"])
                                    conv_out.set_write_destination("OBUF")
                                    cdlt.compute("MVMUL", [data[n, ic, y*stride + kh, x*stride + kw],
                                                           weight[oc, ic, kh, kw],
                                                           bias[oc],
                                                           conv_out[n, oc, y, x]],
                                                 [conv_out[n, oc, y, x]], target="pe_array")

        # TODO: Add store off chip
        cdlt.configure("end", "WBUF")
        cdlt.configure("end", "BBUF")
        cdlt.configure("end", "IBUF")
        cdlt.configure("end", "OBUF")
        cdlt.configure("end", "systolic_array")
        cdlt = add_conv_quant(cdlt, conv_out, out, OC, N, OH, OW)

    cdlt = add_conv_constraints(hag, cdlt, is_fusion=FUSION_CONSTRAINTS)

    return cdlt


## Unquantized versions
def gemm_unquantized(hag: ArchitectureNode):


    with CodeletTemplate("gemm") as cdlt:

        P = cdlt.dummy_op("P", cdlt.node.inputs[2].shape[0])
        N = cdlt.dummy_op("N", cdlt.node.inputs[0].shape[1])
        M = cdlt.dummy_op("M", cdlt.node.inputs[0].shape[0])

        data = cdlt.create_operand_template("data", OP_DTYPES, [M, N], default_dtype=OP_DTYPES[0])
        weight = cdlt.create_operand_template("weight", OP_DTYPES, [N, P], default_dtype=OP_DTYPES[0])
        bias = cdlt.create_operand_template("bias", OP_DTYPES, [P], default_dtype=OP_DTYPES[2])
        out = cdlt.create_operand_template("out", OP_DTYPES, [M, P], default_dtype=OP_DTYPES[2])

        cdlt.set_inputs([data, weight, bias])
        cdlt.set_outputs([out])

        cdlt.configure("start", "systolic_array")
        cdlt.configure("start", "WBUF")
        cdlt.configure("start", "IBUF")
        cdlt.configure("start", "BBUF")
        cdlt.configure("start", "OBUF")
        #
        with cdlt.loop(P) as p:
            with cdlt.loop(N) as n:
                with cdlt.loop(M) as m:
                    cdlt.transfer(data, ["DRAM", "IBUF"])
                    cdlt.transfer(weight, ["DRAM", "WBUF"])
                    cdlt.transfer(bias, ["DRAM", "BBUF"])
                    cdlt.transfer(out, ["DRAM", "OBUF"])
                    out.set_write_destination("OBUF")
                    cdlt.compute("MVMUL", [data[m, n], weight[n, p], bias[p], out[m,p]], [out[m,p]], target="pe_array")
                    cdlt.transfer(out, ["OBUF", "DRAM"])

        # TODO: Add store off chip
        cdlt.configure("end", "WBUF")
        cdlt.configure("end", "IBUF")
        cdlt.configure("end", "OBUF")
        cdlt.configure("end", "BBUF")
        cdlt.configure("end", "systolic_array")

    cdlt = add_gemm_constraints(hag, cdlt)

    return cdlt



def gemm_no_bias_unquantized(hag: ArchitectureNode):

    with CodeletTemplate("matmul") as cdlt:
        P = cdlt.dummy_op("P", cdlt.node.inputs[1].shape[1])
        N = cdlt.dummy_op("N", cdlt.node.inputs[0].shape[1])
        M = cdlt.dummy_op("M", cdlt.node.inputs[0].shape[0])
        data = cdlt.create_operand_template("data", OP_DTYPES, [M, N], default_dtype=OP_DTYPES[0])
        weight = cdlt.create_operand_template("weight", OP_DTYPES, [N, P], default_dtype=OP_DTYPES[0])
        out = cdlt.create_operand_template("out", OP_DTYPES, [M, P], default_dtype=OP_DTYPES[2])


        cdlt.set_inputs([data, weight])
        cdlt.set_outputs([out])

        cdlt.configure("start", "systolic_array")
        cdlt.configure("start", "WBUF")
        cdlt.configure("start", "IBUF")
        cdlt.configure("start", "OBUF")

        with cdlt.loop(M) as m:
            with cdlt.loop(N) as n:
                with cdlt.loop(P) as p:
                    cdlt.transfer(data, ["DRAM", "IBUF"])
                    cdlt.transfer(weight, ["DRAM", "WBUF"])
                    cdlt.transfer(out, ["DRAM", "OBUF"])
                    out.set_write_destination("OBUF")
                    cdlt.compute("MVMUL", [data[m, n], weight[n, p], out[m,p]], [out[m,p]], target="pe_array")
                    cdlt.transfer(out, ["OBUF", "DRAM"])

        # TODO: Add store off chip
        cdlt.configure("end", "WBUF")
        cdlt.configure("end", "IBUF")
        cdlt.configure("end", "OBUF")
        cdlt.configure("end", "systolic_array")

    cdlt = add_gemm_constraints(hag, cdlt)

    return cdlt



def conv2d_unquantized(hag: ArchitectureNode):
    # TODO: Need to figure out how to change the memory layout
    with CodeletTemplate("conv") as cdlt:
        stride = cdlt.dummy_op("stride", cdlt.node.stride)
        pad = cdlt.dummy_op("pad", cdlt.node.pad_int)
        OC = cdlt.dummy_op("OC", cdlt.node.outputs[0].shape[1])
        N = cdlt.dummy_op("N", cdlt.node.inputs[0].shape[0])
        IC = cdlt.dummy_op("IC", cdlt.node.inputs[0].shape[1])
        KH = cdlt.dummy_op("KH", cdlt.node.inputs[1].shape[2])
        KW = cdlt.dummy_op("KW", cdlt.node.inputs[1].shape[3])
        OH = cdlt.dummy_op("OH", cdlt.node.outputs[0].shape[2])
        OW = cdlt.dummy_op("OW", cdlt.node.outputs[0].shape[3])
        IH = cdlt.dummy_op("IH", cdlt.node.inputs[0].shape[2])
        IW = cdlt.dummy_op("IW", cdlt.node.inputs[0].shape[3])

        data = cdlt.create_operand_template("data", OP_DTYPES, [N, IC, IH, IW], default_dtype=OP_DTYPES[0])
        weight = cdlt.create_operand_template("weight", OP_DTYPES, [OC, IC, KH, KW], default_dtype=OP_DTYPES[0])
        out = cdlt.create_operand_template("out", OP_DTYPES, [N, OC, OH, OW], default_dtype=OP_DTYPES[2])
        cdlt.set_inputs([data, weight])
        cdlt.set_outputs([out])
        cdlt.configure("start", "systolic_array")
        cdlt.configure("start", "WBUF")
        cdlt.configure("start", "BBUF")
        cdlt.configure("start", "IBUF")
        cdlt.configure("start", "OBUF")
        # OS ->
        with cdlt.loop(OC) as oc:
            with cdlt.loop(N) as n:
                with cdlt.loop(IC) as ic:
                    with cdlt.loop(KH) as kh:
                        with cdlt.loop(KW) as kw:
                            with cdlt.loop(OH) as y:
                                with cdlt.loop(OW) as x:
                                    cdlt.transfer(weight, ["DRAM", "WBUF"])
                                    cdlt.transfer(data, ["DRAM", "IBUF"])
                                    cdlt.transfer(out, ["DRAM", "OBUF"])
                                    out.set_write_destination("OBUF")
                                    cdlt.compute("MVMUL", [data[n, ic, y*stride + kh, x*stride + kw],
                                                           weight[oc, ic, kh, kw],
                                                           out[n, oc, y, x]],
                                                 [out[n, oc, y, x]], target="pe_array")
                                    cdlt.transfer(out, ["OBUF", "DRAM"])


        # TODO: Add store off chip
        cdlt.configure("end", "WBUF")
        cdlt.configure("end", "BBUF")
        cdlt.configure("end", "IBUF")
        cdlt.configure("end", "OBUF")
        cdlt.configure("end", "systolic_array")

    cdlt = add_conv_constraints(hag, cdlt, is_fusion=FUSION_CONSTRAINTS)
    return cdlt

def conv2d_bias_unquantized(hag: ArchitectureNode):
    # TODO: Need to figure out how to change the memory layout

    required_params = {}

    with CodeletTemplate("conv_bias") as cdlt:
        stride = cdlt.dummy_op("stride", cdlt.node.stride)
        pad = cdlt.dummy_op("pad", cdlt.node.pad_int)
        OC = cdlt.dummy_op("OC", cdlt.node.outputs[0].shape[1])
        N = cdlt.dummy_op("N", cdlt.node.inputs[0].shape[0])
        IC = cdlt.dummy_op("IC", cdlt.node.inputs[0].shape[1])
        KH = cdlt.dummy_op("KH", cdlt.node.inputs[1].shape[2])
        KW = cdlt.dummy_op("KW", cdlt.node.inputs[1].shape[3])
        OH = cdlt.dummy_op("OH", cdlt.node.outputs[0].shape[2])
        OW = cdlt.dummy_op("OW", cdlt.node.outputs[0].shape[3])
        IH = cdlt.dummy_op("IH", cdlt.node.inputs[0].shape[2])
        IW = cdlt.dummy_op("IW", cdlt.node.inputs[0].shape[3])

        data = cdlt.create_operand_template("data", OP_DTYPES, [N, IC, IH, IW], default_dtype=OP_DTYPES[0])
        weight = cdlt.create_operand_template("weight", OP_DTYPES, [OC, IC, KH, KW], default_dtype=OP_DTYPES[0])
        bias = cdlt.create_operand_template("bias", OP_DTYPES, [OC], default_dtype=OP_DTYPES[2])
        out = cdlt.create_operand_template("out", OP_DTYPES, [N, OC, OH, OW], default_dtype=OP_DTYPES[2])

        cdlt.set_inputs([data, weight, bias])
        cdlt.set_outputs([out])

        cdlt.configure("start", "systolic_array")
        cdlt.configure("start", "WBUF")
        cdlt.configure("start", "BBUF")
        cdlt.configure("start", "IBUF")
        cdlt.configure("start", "OBUF")
        with cdlt.loop(OC) as oc:
            with cdlt.loop(N) as n:
                with cdlt.loop(IC) as ic:
                    with cdlt.loop(KH) as kh:
                        with cdlt.loop(KW) as kw:
                            with cdlt.loop(OH) as y:
                                with cdlt.loop(OW) as x:
                                    cdlt.transfer(weight, ["DRAM", "WBUF"])
                                    cdlt.transfer(bias, ["DRAM", "BBUF"])
                                    cdlt.transfer(data, ["DRAM", "IBUF"])
                                    cdlt.transfer(out, ["DRAM", "OBUF"])
                                    out.set_write_destination("OBUF")
                                    cdlt.compute("MVMUL", [data[n, ic, y*stride + kh, x*stride + kw],
                                                           weight[oc, ic, kh, kw],
                                                           bias[oc],
                                                           out[n, oc, y, x]],
                                                 [out[n, oc, y, x]], target="pe_array")
                                    cdlt.transfer(out, ["OBUF", "DRAM"])


        # TODO: Add store off chip
        cdlt.configure("end", "WBUF")
        cdlt.configure("end", "BBUF")
        cdlt.configure("end", "IBUF")
        cdlt.configure("end", "OBUF")
        cdlt.configure("end", "systolic_array")

    cdlt = add_conv_constraints(hag, cdlt, is_fusion=FUSION_CONSTRAINTS)
    return cdlt

if USE_QUANTIZATION:
    SA_CDLTS = {
        "conv_bias": conv2d_bias,
        "conv": conv2d,
        "gemm": gemm,
        'matmul': gemm_no_bias,
        'matmul4d': matmul4d
    }
else:
    SA_CDLTS = {
        "conv_bias": conv2d_bias_unquantized,
        "conv": conv2d_unquantized,
        "gemm": gemm_unquantized,
        'matmul': gemm_no_bias_unquantized,
        'matmul4d': matmul4d_no_quant

    }