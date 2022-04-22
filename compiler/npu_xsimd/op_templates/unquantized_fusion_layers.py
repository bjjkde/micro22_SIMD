from op_templates.adl.graph import ArchitectureNode
from op_templates.templates.op_template import CodeletTemplate
from examples.genesys import OP_DTYPES, ASIC_CONFIG, \
    FXP_CONFIGS, QUANT_SCALE, SIGN_SHIFT, SW_PIPELINE_TEST, ALL_QUANT_OFF, FUSION_CONSTRAINTS
from . import add_conv_constraints, range_from_cfg, \
    add_simd_constraint, create_immediate_with_operand, add_scale_op, \
    add_simd_tile_constraint, add_gemm_constraints, add_scale_and_cast_op

def create_matmul3d_args(cdlt):
    params = {}
    B = cdlt.dummy_op("B", cdlt.node.inputs[0].shape[0])
    M = cdlt.dummy_op("M", cdlt.node.inputs[0].shape[1])
    N = cdlt.dummy_op("N", cdlt.node.inputs[0].shape[2])
    P = cdlt.dummy_op("P", cdlt.node.inputs[1].shape[1])

    params['B'] = B
    params['M'] = M
    params['N'] = N
    params['P'] = P

    data = cdlt.create_operand_template("data", OP_DTYPES, [B, M, N], default_dtype=OP_DTYPES[0])
    weight = cdlt.create_operand_template("weight", OP_DTYPES, [N, P], default_dtype=OP_DTYPES[0])
    bias = cdlt.create_operand_template("bias", OP_DTYPES, [P], default_dtype=OP_DTYPES[2])
    cdlt.set_inputs([data, weight, bias])
    return cdlt, params

def create_matmul4d_args(cdlt):
    params = {}
    B = cdlt.dummy_op("B", cdlt.node.inputs[0].shape[0])
    C = cdlt.dummy_op("C", cdlt.node.inputs[0].shape[1])
    M = cdlt.dummy_op("M", cdlt.node.inputs[0].shape[2])
    N = cdlt.dummy_op("N", cdlt.node.inputs[0].shape[3])
    P = cdlt.dummy_op("P", cdlt.node.inputs[1].shape[3])

    params['B'] = B
    params['M'] = M
    params['C'] = C
    params['N'] = N
    params['P'] = P

    data = cdlt.create_operand_template("data", OP_DTYPES, [B, C, M, N], default_dtype=OP_DTYPES[0])
    weight = cdlt.create_operand_template("weight", OP_DTYPES, [B, C, N, P], default_dtype=OP_DTYPES[0])

    cdlt.set_inputs([data, weight])
    return cdlt, params

def create_mamtul4d_func(cdlt, params):
    data = cdlt.inputs[0]
    weight = cdlt.inputs[1]
    B = params['B']
    M = params['M']
    N = params['N']
    C = params['C']
    P = params['P']

    gemm_out = cdlt.create_operand_template("gemm_out", OP_DTYPES, [B, C, M, P], default_dtype=OP_DTYPES[2])
    cdlt.add_temp_operand(gemm_out)

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
                        cdlt.compute("MVMUL", [data[b, c, m, n], weight[b, c, n, p], gemm_out[b, c, m, p]],
                                     [gemm_out[b, c, m, p]], target="pe_array")
        # TODO: Add store off chip
    cdlt.configure("end", "WBUF")
    cdlt.configure("end", "IBUF")
    cdlt.configure("end", "OBUF")
    cdlt.configure("end", "systolic_array")

    return cdlt, gemm_out

def create_mamtul3d_func(cdlt, params):
    data = cdlt.inputs[0]
    weight = cdlt.inputs[1]
    bias = cdlt.inputs[2]
    B = params['B']
    M = params['M']
    N = params['N']
    P = params['P']

    gemm_out = cdlt.create_operand_template("gemm_out", OP_DTYPES, [B, M, P], default_dtype=OP_DTYPES[2])
    cdlt.add_temp_operand(gemm_out)


    cdlt.configure("start", "systolic_array")
    cdlt.configure("start", "WBUF")
    cdlt.configure("start", "IBUF")
    cdlt.configure("start", "OBUF")
    cdlt.configure("start", "BBUF")
    with cdlt.loop(B) as b:
        with cdlt.loop(M) as m:
            with cdlt.loop(N) as n:
                with cdlt.loop(P) as p:
                    cdlt.transfer(data, ["DRAM", "IBUF"])
                    cdlt.transfer(weight, ["DRAM", "WBUF"])
                    cdlt.transfer(bias, ["DRAM", "BBUF"])
                    cdlt.transfer(gemm_out, ["DRAM", "OBUF"])
                    gemm_out.set_write_destination("OBUF")
                    cdlt.compute("MVMUL", [data[b, m, n], weight[n, p], bias[p], gemm_out[b, m, p]], [gemm_out[b, m, p]], target="pe_array")
    # TODO: Add store off chip
    cdlt.configure("end", "WBUF")
    cdlt.configure("end", "IBUF")
    cdlt.configure("end", "OBUF")
    cdlt.configure("end", "BBUF")
    cdlt.configure("end", "systolic_array")
    return cdlt, gemm_out

def create_conv_args(cdlt):
    params = {}
    stride = cdlt.dummy_op("stride", cdlt.node.stride)
    pad = cdlt.dummy_op("pad", cdlt.node.pad_int)
    OC = cdlt.dummy_op("OC", cdlt.node.conv_output.shape[1])
    N = cdlt.dummy_op("N", cdlt.node.inputs[0].shape[0])
    OH = cdlt.dummy_op("OH", cdlt.node.conv_output.shape[2])
    OW = cdlt.dummy_op("OW", cdlt.node.conv_output.shape[3])
    IC = cdlt.dummy_op("IC", cdlt.node.inputs[0].shape[1])
    KH = cdlt.dummy_op("KH", cdlt.node.inputs[1].shape[2])
    KW = cdlt.dummy_op("KW", cdlt.node.inputs[1].shape[3])
    IH = cdlt.dummy_op("IH", cdlt.node.inputs[0].shape[2])
    IW = cdlt.dummy_op("IW", cdlt.node.inputs[0].shape[3])

    params['stride'] = stride
    params['pad'] = pad
    params['OC'] = OC
    params['N'] = N
    params['IC'] = IC
    params['OH'] = OH
    params['OW'] = OW
    params['KH'] = KH
    params['KW'] = KW
    params['IH'] = IH
    params['IW'] = IW

    data = cdlt.create_operand_template("data", OP_DTYPES, [N, IC, IH, IW], default_dtype=OP_DTYPES[0])
    weight = cdlt.create_operand_template("weight", OP_DTYPES, [OC, IC, KH, KW], default_dtype=OP_DTYPES[0])
    bias = cdlt.create_operand_template("bias", OP_DTYPES, [OC], default_dtype=OP_DTYPES[2])
    cdlt.set_inputs([data, weight, bias])
    return cdlt, params


def create_conv_func(cdlt, params):
    data = cdlt.inputs[0]
    weight = cdlt.inputs[1]
    bias = cdlt.inputs[2]
    stride = params['stride']
    pad = params['pad']
    OC = params['OC']
    N = params['N']
    IC = params['IC']
    OH = params['OH']
    OW = params['OW']
    KH = params['KH']
    KW = params['KW']
    IH = params['IH']
    IW = params['IW']

    conv_out = cdlt.create_operand_template("conv_out", OP_DTYPES, [N, OC, OH, OW], default_dtype=OP_DTYPES[2])
    cdlt.add_temp_operand(conv_out)
    # SA Config
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
                                cdlt.compute("MVMUL",
                                             [data[n, ic, y * stride + kh, x * stride + kw], weight[oc, ic, kh, kw],
                                              bias[oc], conv_out[n, oc, y, x]], [conv_out[n, oc, y, x]],
                                             target="pe_array")
    # TODO: Add store off chip
    cdlt.configure("end", "WBUF")
    cdlt.configure("end", "BBUF")
    cdlt.configure("end", "IBUF")
    cdlt.configure("end", "OBUF")
    cdlt.configure("end", "systolic_array")
    return cdlt, conv_out

def conv_relu(hag: ArchitectureNode):
    with CodeletTemplate("conv_bias_relu") as cdlt:

        cdlt, params = create_conv_args(cdlt)
        SIMD_SIZE = cdlt.dummy_op("SIMD_SIZE", cdlt.hag.all_subgraph_nodes['SIMD'].dimensions[0])
        param = cdlt.create_temp_operand([SIMD_SIZE], "IMM")
        cdlt, conv_out = create_conv_func(cdlt, params)

        OC, N, OH, OW = params['OC'], params['N'], params['OH'], params['OW']
        relu_out = cdlt.create_operand_template("relu_out", OP_DTYPES, [N, OC, OH, OW], default_dtype=OP_DTYPES[2])
        relu_out.start_location = "VMEM1"
        cdlt.add_temp_operand(relu_out)

        out = cdlt.create_operand_template("out", OP_DTYPES, [N, OC, OH, OW], default_dtype=OP_DTYPES[0])
        cdlt.set_outputs([out])

        cdlt.configure("start", "SIMD")
        m0 = create_immediate_with_operand(cdlt, QUANT_SCALE, simd_size=SIMD_SIZE)
        nshift = create_immediate_with_operand(cdlt, SIGN_SHIFT, simd_size=SIMD_SIZE)
        cdlt.configure("start", "IMM", immediate_value=16, index=0)
        with cdlt.loop(OC) as oc:
            with cdlt.loop(N) as n:
                with cdlt.loop(OH) as y:
                    with cdlt.loop(OW) as x:
                        out.set_write_destination("VMEM2")
                        relu_out.set_write_destination("VMEM1")
                        indices = (n, oc, y, x)
                        cdlt.compute("RELU", [conv_out[n, oc, y, x], param], [relu_out[n, oc, y, x]], target="SIMD")
                        cdlt.compute("32FXP_8FXP", [relu_out[n, oc, y, x]], [out[n, oc, y, x]], target="SIMD")
                        cdlt.transfer(out, ["VMEM2", "DRAM"])
        cdlt.configure("end", "SIMD")

    cdlt = add_conv_constraints(hag, cdlt, is_fusion=True)

    return cdlt


def conv_leaky_relu(hag: ArchitectureNode):
    with CodeletTemplate("conv_bias_leaky_relu") as cdlt:

        cdlt, params = create_conv_args(cdlt)
        SIMD_SIZE = cdlt.dummy_op("SIMD_SIZE", cdlt.hag.all_subgraph_nodes['SIMD'].dimensions[0])
        alpha = cdlt.create_temp_operand([SIMD_SIZE], "IMM")
        cdlt, conv_out = create_conv_func(cdlt, params)

        OC, N, OH, OW = params['OC'], params['N'], params['OH'], params['OW']


        out = cdlt.create_operand_template("out", OP_DTYPES, [N, OC, OH, OW], default_dtype=OP_DTYPES[0])
        cdlt.set_outputs([out])

        cdlt.configure("start", "SIMD")
        alphaval = cdlt.dummy_op("alpha", cdlt.node.alpha, dtype="FXP32")
        m0 = create_immediate_with_operand(cdlt, QUANT_SCALE, simd_size=SIMD_SIZE)
        nshift = create_immediate_with_operand(cdlt, SIGN_SHIFT, simd_size=SIMD_SIZE)
        cdlt.configure("start", "IMM", immediate_value=alphaval, index=0)
        with cdlt.loop(OC) as oc:
            with cdlt.loop(N) as n:
                with cdlt.loop(OH) as y:
                    with cdlt.loop(OW) as x:
                        out.set_write_destination("VMEM2")
                        ## Scaling
                        indices = (n, oc, y, x)
                        cdlt.compute("LEAKY_RELU", [conv_out[n, oc, y, x], alpha], [out[n, oc, y, x]], target="SIMD")
                        cdlt.transfer(out, ["VMEM2", "DRAM"])
        cdlt.configure("end", "SIMD")

    cdlt = add_conv_constraints(hag, cdlt, is_fusion=True)

    return cdlt


def conv_relu_max_pool(hag: ArchitectureNode):
    with CodeletTemplate("conv_bias_relu_max_pool") as cdlt:
        # Setup conv arguments
        cdlt, params = create_conv_args(cdlt)
        # Add parameter for relu
        SIMD_SIZE = cdlt.dummy_op("SIMD_SIZE", cdlt.hag.all_subgraph_nodes['SIMD'].dimensions[0])
        param = cdlt.create_temp_operand([SIMD_SIZE], "IMM")

        # Create systolic loop nest
        cdlt, conv_out = create_conv_func(cdlt, params)

        # parameters for max pool
        C, N = params['OC'], params['N']
        OH = cdlt.dummy_op("OH1", cdlt.node.outputs[0].shape[2])
        OW = cdlt.dummy_op("OW1", cdlt.node.outputs[0].shape[3])
        KH = cdlt.dummy_op("KH1", cdlt.node.kernel_size[0])
        KW = cdlt.dummy_op("KW1", cdlt.node.kernel_size[1])

        # Create outputs
        out = cdlt.create_operand_template("out", OP_DTYPES, [N, C, OH, OW], default_dtype=OP_DTYPES[2])
        cdlt.set_outputs([out])

        # Create temporary storage for relu output
        relu_out = cdlt.create_operand_template("relu_out", OP_DTYPES, [N, C, params['OH'], params['OW']], default_dtype=OP_DTYPES[2])
        relu_out.start_location = "VMEM1"
        cdlt.add_temp_operand(relu_out)


        min_val, _ = range_from_cfg(FXP_CONFIGS[str(OP_DTYPES[2])])
        mp_pad = cdlt.dummy_op("max_pool_pad", cdlt.node.pad0[0])
        sy = cdlt.dummy_op("sy", cdlt.node.stride0[0])
        sx = cdlt.dummy_op("sx", cdlt.node.stride0[1])
        cdlt.configure("start", "SIMD")
        cdlt.configure("start", "IMM", immediate_value=min_val, index=0)
        with cdlt.loop(N) as n:
            with cdlt.loop(C) as c:
                with cdlt.loop(KH) as kh:
                    with cdlt.loop(KW) as kw:
                        with cdlt.loop(OH) as y:
                            with cdlt.loop(OW) as x:
                                cdlt.transfer(out, ["DRAM", "VMEM2"])
                                out.set_write_destination("VMEM2")
                                relu_out.set_write_destination("VMEM1")
                                cdlt.compute("RELU", [conv_out[n, c, y * sy + kh, x * sx + kw], param],
                                             [relu_out[n, c, y * sy + kh, x * sx + kw]], target="SIMD")
                                cdlt.compute("MAX", [relu_out[n, c, y * sy + kh, x * sx + kw],
                                                     out[n, c, y, x]],
                                             [out[n, c, y, x]], target="SIMD")
                                cdlt.transfer(out, ["VMEM2", "DRAM"])
        cdlt.configure("end", "SIMD")
    cdlt = add_conv_constraints(hag, cdlt, is_fusion=True)
    cdlt = add_simd_constraint(hag, cdlt, "OC")
    return cdlt


def conv_add_relu(hag: ArchitectureNode):

    with CodeletTemplate("conv_bias_add_relu") as cdlt:
        cdlt, params = create_conv_args(cdlt)

        # Use initial params to setup subsequent operation details
        OC, N, OH, OW = params['OC'], params['N'], params['OH'], params['OW']
        SIMD_SIZE = cdlt.dummy_op("SIMD_SIZE", cdlt.hag.all_subgraph_nodes['SIMD'].dimensions[0])
        param = cdlt.create_temp_operand([SIMD_SIZE], "IMM")
        add_lhs = cdlt.create_operand_template("add_lhs", OP_DTYPES, [N, OC, OH, OW], default_dtype=OP_DTYPES[2])
        out = cdlt.create_operand_template("out", OP_DTYPES, [N, OC, OH, OW], default_dtype=OP_DTYPES[2])
        cdlt.add_input(add_lhs)
        cdlt.set_outputs([out])

        add_out = cdlt.create_operand_template("add_out", OP_DTYPES, [N, OC, OH, OW], default_dtype=OP_DTYPES[2])
        add_out.start_location = "VMEM2"
        cdlt.add_temp_operand(add_out)

        # Add the convolution
        cdlt, conv_out = create_conv_func(cdlt, params)

        cdlt.configure("start", "SIMD")
        m0 = create_immediate_with_operand(cdlt, QUANT_SCALE, simd_size=SIMD_SIZE)
        nshift = create_immediate_with_operand(cdlt, SIGN_SHIFT, simd_size=SIMD_SIZE)
        cdlt.configure("start", "IMM", immediate_value=16, index=0)
        with cdlt.loop(OC) as oc:
            with cdlt.loop(N) as n:
                with cdlt.loop(OH) as y:
                    with cdlt.loop(OW) as x:
                        cdlt.transfer(add_lhs, ["DRAM", "VMEM1"])
                        out.set_write_destination("VMEM1")
                        add_out.set_write_destination("VMEM2")

                        indices = (n, oc, y, x)
                        cdlt.compute("ADD", [add_lhs[n, oc, y, x], conv_out[n, oc, y, x]], [add_out[n, oc, y, x]],
                                     target="SIMD")
                        cdlt.compute("RELU", [add_out[n, oc, y, x], param], [out[n, oc, y, x]], target="SIMD")
                        cdlt.transfer(out, ["VMEM1", "DRAM"])
        cdlt.configure("end", "SIMD")

    cdlt = add_conv_constraints(hag, cdlt, is_fusion=True)

    return cdlt

def conv_add(hag: ArchitectureNode):

    with CodeletTemplate("conv_bias_add") as cdlt:
        cdlt, params = create_conv_args(cdlt)

        # Use initial params to setup subsequent operation details
        OC, N, OH, OW = params['OC'], params['N'], params['OH'], params['OW']
        SIMD_SIZE = cdlt.dummy_op("SIMD_SIZE", cdlt.hag.all_subgraph_nodes['SIMD'].dimensions[0])
        add_lhs = cdlt.create_operand_template("add_lhs", OP_DTYPES, [N, OC, OH, OW], default_dtype=OP_DTYPES[2])
        out = cdlt.create_operand_template("out", OP_DTYPES, [N, OC, OH, OW], default_dtype=OP_DTYPES[2])
        cdlt.add_input(add_lhs)
        cdlt.set_outputs([out])


        # Add the convolution
        cdlt, conv_out = create_conv_func(cdlt, params)

        cdlt.configure("start", "SIMD")
        m0 = create_immediate_with_operand(cdlt, QUANT_SCALE, simd_size=SIMD_SIZE)
        nshift = create_immediate_with_operand(cdlt, SIGN_SHIFT, simd_size=SIMD_SIZE)
        cdlt.configure("start", "IMM", immediate_value=16, index=0)
        with cdlt.loop(OC) as oc:
            with cdlt.loop(N) as n:
                with cdlt.loop(OH) as y:
                    with cdlt.loop(OW) as x:
                        cdlt.transfer(add_lhs, ["DRAM", "VMEM1"])
                        out.set_write_destination("VMEM1")
                        indices = (n, oc, y, x)
                        cdlt.compute("ADD", [add_lhs[n, oc, y, x], conv_out[n, oc, y, x]], [out[n, oc, y, x]],
                                     target="SIMD")
                        cdlt.transfer(out, ["VMEM1", "DRAM"])
        cdlt.configure("end", "SIMD")

    cdlt = add_conv_constraints(hag, cdlt, is_fusion=True)

    return cdlt


def conv_add_leaky_relu(hag: ArchitectureNode):

    with CodeletTemplate("conv_bias_add_leaky_relu") as cdlt:
        cdlt, params = create_conv_args(cdlt)

        # Use initial params to setup subsequent operation details
        OC, N, OH, OW = params['OC'], params['N'], params['OH'], params['OW']
        SIMD_SIZE = cdlt.dummy_op("SIMD_SIZE", cdlt.hag.all_subgraph_nodes['SIMD'].dimensions[0])
        alpha = cdlt.create_temp_operand([SIMD_SIZE], "IMM")
        add_lhs = cdlt.create_operand_template("add_lhs", OP_DTYPES, [N, OC, OH, OW], default_dtype=OP_DTYPES[2])
        out = cdlt.create_operand_template("out", OP_DTYPES, [N, OC, OH, OW], default_dtype=OP_DTYPES[0])
        cdlt.add_input(add_lhs)
        cdlt.set_outputs([out])

        add_out = cdlt.create_operand_template("add_out", OP_DTYPES, [N, OC, OH, OW], default_dtype=OP_DTYPES[2])
        add_out.start_location = "VMEM2"
        cdlt.add_temp_operand(add_out)

        # Add the convolution
        cdlt, conv_out = create_conv_func(cdlt, params)

        cdlt.configure("start", "SIMD")
        m0 = create_immediate_with_operand(cdlt, QUANT_SCALE, simd_size=SIMD_SIZE)
        nshift = create_immediate_with_operand(cdlt, SIGN_SHIFT, simd_size=SIMD_SIZE)
        alphaval = cdlt.dummy_op("alpha", cdlt.node.alpha, dtype="FXP32")
        cdlt.configure("start", "IMM", immediate_value=alphaval, index=0)
        with cdlt.loop(OC) as oc:
            with cdlt.loop(N) as n:
                with cdlt.loop(OH) as y:
                    with cdlt.loop(OW) as x:
                        cdlt.transfer(add_lhs, ["DRAM", "VMEM1"])
                        out.set_write_destination("VMEM1")
                        add_out.set_write_destination("VMEM2")
                        indices = (n, oc, y, x)
                        cdlt.compute("ADD", [add_lhs[n, oc, y, x], conv_out[n, oc, y, x]], [add_out[n, oc, y, x]],
                                     target="SIMD")
                        cdlt.compute("LEAKY_RELU", [add_out[n, oc, y, x], alpha], [out[n, oc, y, x]], target="SIMD")

                        cdlt.transfer(out, ["VMEM1", "DRAM"])
        cdlt.configure("end", "SIMD")

    cdlt = add_conv_constraints(hag, cdlt, is_fusion=True)

    return cdlt

def conv_leaky_relu_add(hag: ArchitectureNode):
    # MP padding:
    # iw1' = ((ow_conv + 2*p_mp) - 1) * stride + kw_conv
    # P1_update = (iw' - iw1)/2
    # Halo effect
    # constraint =
    with CodeletTemplate("conv_bias_leaky_relu_add") as cdlt:
        cdlt, params = create_conv_args(cdlt)

        # Use initial params to setup subsequent operation details
        OC, N, OH, OW = params['OC'], params['N'], params['OH'], params['OW']
        SIMD_SIZE = cdlt.dummy_op("SIMD_SIZE", cdlt.hag.all_subgraph_nodes['SIMD'].dimensions[0])
        alpha = cdlt.create_temp_operand([SIMD_SIZE], "IMM")
        add_lhs = cdlt.create_operand_template("add_lhs", OP_DTYPES, [N, OC, OH, OW], default_dtype=OP_DTYPES[2])
        out = cdlt.create_operand_template("out", OP_DTYPES, [N, OC, OH, OW], default_dtype=OP_DTYPES[0])
        cdlt.add_input(add_lhs)
        cdlt.set_outputs([out])

        leaky_relu_out = cdlt.create_operand_template("leaky_relu_out", OP_DTYPES, [N, OC, OH, OW], default_dtype=OP_DTYPES[2])
        leaky_relu_out.start_location = "VMEM2"
        cdlt.add_temp_operand(leaky_relu_out)

        # Add the convolution
        cdlt, conv_out = create_conv_func(cdlt, params)

        cdlt.configure("start", "SIMD")
        m0 = create_immediate_with_operand(cdlt, QUANT_SCALE, simd_size=SIMD_SIZE)
        nshift = create_immediate_with_operand(cdlt, SIGN_SHIFT, simd_size=SIMD_SIZE)
        alphaval = cdlt.dummy_op("alpha", cdlt.node.alpha, dtype="FXP32")
        cdlt.configure("start", "IMM", immediate_value=alphaval, index=0)
        with cdlt.loop(OC) as oc:
            with cdlt.loop(N) as n:
                with cdlt.loop(OH) as y:
                    with cdlt.loop(OW) as x:
                        cdlt.transfer(add_lhs, ["DRAM", "VMEM1"])
                        out.set_write_destination("VMEM1")
                        leaky_relu_out.set_write_destination("VMEM2")
                        add_lhs.set_write_destination("VMEM1")

                        indices = (n, oc, y, x)
                        cdlt.compute("LEAKY_RELU", [conv_out[n, oc, y, x], alpha], [leaky_relu_out[n, oc, y, x]], target="SIMD")
                        cdlt.compute("ADD", [add_lhs[n, oc, y, x], leaky_relu_out[n, oc, y, x]], [out[n, oc, y, x]], target="SIMD")
                        cdlt.transfer(out, ["VMEM1", "DRAM"])
        cdlt.configure("end", "SIMD")

    cdlt = add_conv_constraints(hag, cdlt, is_fusion=True)

    return cdlt

def conv_bias_clip_depthwise_conv_bias(hag: ArchitectureNode):

    with CodeletTemplate("conv_bias_clip_depthwise_conv_bias") as cdlt:
        # Setup conv arguments
        cdlt, params = create_conv_args(cdlt)
        # Add parameter for clip
        C, N = params['OC'], params['N']
        ONE = cdlt.dummy_op("ONE", cdlt.node.inputs[3].shape[1])
        OH = cdlt.dummy_op("OH1", cdlt.node.outputs[0].shape[2])
        OW = cdlt.dummy_op("OW1", cdlt.node.outputs[0].shape[3])
        KH = cdlt.dummy_op("KH1", cdlt.node.inputs[3].shape[2])
        KW = cdlt.dummy_op("KW1", cdlt.node.inputs[3].shape[3])

        # Add dw conv inputs
        weight = cdlt.create_operand_template("dw_conv_wgt", OP_DTYPES, [C, ONE, KH, KW], default_dtype=OP_DTYPES[2])
        bias = cdlt.create_operand_template("dw_conv_bias", OP_DTYPES, [C], default_dtype=OP_DTYPES[2])
        cdlt.add_input(weight)
        cdlt.add_input(bias)

        s = cdlt.dummy_op("s2", cdlt.node.stride0)
        pad = cdlt.dummy_op("p2", cdlt.node.pad_int0)


        # Create outputs
        out = cdlt.create_operand_template("out", OP_DTYPES, [N, C, OH, OW], default_dtype=OP_DTYPES[0])
        cdlt.set_outputs([out])

        # Create temporary storage
        clip_out1 = cdlt.create_operand_template("clip_out1", OP_DTYPES, [N, C, params['OH'], params['OW']], default_dtype=OP_DTYPES[2])
        cdlt.add_temp_operand(clip_out1)

        dw_conv_out = cdlt.create_operand_template("dw_conv_out", OP_DTYPES, [N, C, params['OH'], params['OW']], default_dtype=OP_DTYPES[2])
        cdlt.add_temp_operand(dw_conv_out)

        # clip_out2 = cdlt.create_operand_template("clip_out2", OP_DTYPES, [N, C, params['OH'], params['OW']], default_dtype=OP_DTYPES[2])


        # Setup min/max params
        minval = cdlt.dummy_op("min", cdlt.node.kwargs['minval'], dtype="FXP32")
        maxval = cdlt.dummy_op("max", cdlt.node.kwargs['maxval'], dtype="FXP32")
        SIMD_SIZE = cdlt.dummy_op("SIMD_SIZE", cdlt.hag.all_subgraph_nodes['SIMD'].dimensions[0])

        min_op = cdlt.create_temp_operand([SIMD_SIZE], "IMM")
        max_op = cdlt.create_temp_operand([SIMD_SIZE], "IMM")

        cdlt, conv_out = create_conv_func(cdlt, params)
        cdlt.configure("start", "SIMD")
        m0 = create_immediate_with_operand(cdlt, QUANT_SCALE, simd_size=SIMD_SIZE)
        nshift = create_immediate_with_operand(cdlt, SIGN_SHIFT, simd_size=SIMD_SIZE)
        zero = create_immediate_with_operand(cdlt, 0, simd_size=SIMD_SIZE)
        cdlt.configure("start", "IMM", immediate_value=minval, index=len(cdlt.temps) + 1)
        cdlt.configure("start", "IMM", immediate_value=maxval, index=len(cdlt.temps) + 2)
        with cdlt.loop(ONE) as one:
            with cdlt.loop(N) as n:
                with cdlt.loop(C) as c:
                    with cdlt.loop(OH) as y:
                        with cdlt.loop(OW) as x:
                            with cdlt.loop(KH) as kh:
                                with cdlt.loop(KW) as kw:
                                    cdlt.transfer(weight, ["DRAM", "VMEM1"])
                                    cdlt.transfer(bias, ["DRAM", "VMEM2"])
                                    clip_out1.set_write_destination("VMEM2")
                                    dw_conv_out.set_write_destination("VMEM1")
                                    indices = (n, c, y * s + kh, x * s + kw)

                                    cdlt.compute("MAX", [conv_out[n, c, y * s + kh, x * s + kw], max_op],
                                                 [clip_out1[n, c, y * s + kh, x * s + kw]
                                                  ],
                                                 target="SIMD")

                                    cdlt.compute("MIN", [clip_out1[n, c, y * s + kh, x * s + kw], min_op],
                                                 [clip_out1[n, c, y * s + kh, x * s + kw]],
                                                 target="SIMD")
                                    cdlt.compute("MOVE", [zero], [dw_conv_out[n, c ,y , x]], target="SIMD")
                                    cdlt.compute("MACC",
                                                 [clip_out1[n, c, y * s + kh, x * s + kw], weight[c, one, kh, kw],
                                                  dw_conv_out[n, c, y, x]], [dw_conv_out[n, c, y, x]],
                                                 target="SIMD")

                                    cdlt.compute("ADD", [dw_conv_out[n, c, y, x], bias[c]], [out[n,c,y,x]], target="SIMD")
                                    indices = (n, c, y, x)
                                    out.set_write_destination("VMEM1")

                                    cdlt.transfer(out, ["VMEM1", "DRAM"])

        cdlt.configure("end", "SIMD")
    cdlt = add_conv_constraints(hag, cdlt, is_fusion=True)
    cdlt = add_simd_constraint(hag, cdlt, "OC")
    cdlt = add_simd_tile_constraint(hag, cdlt, ["KH1", "KW1"])
    cdlt.update_compilation_param("LEVEL1_hint", "sizes['OH'] == (sizes['OH1'] - 1)*params['s2'] + sizes['KH1'] and splits['OH1'] == splits['OH']")
    cdlt.update_compilation_param("LEVEL1_hint", "sizes['OW'] == (sizes['OW1'] - 1)*params['s2'] + sizes['KW1'] and splits['OW1'] == splits['OW']")

    return cdlt


def conv_bias_clip_depthwise_conv_bias_clip(hag: ArchitectureNode):

    with CodeletTemplate("conv_bias_clip_depthwise_conv_bias_clip") as cdlt:
        # Setup conv arguments
        cdlt, params = create_conv_args(cdlt)
        # Add parameter for clip
        C, N = params['OC'], params['N']
        ONE = cdlt.dummy_op("ONE", cdlt.node.inputs[3].shape[1])
        OH = cdlt.dummy_op("OH1", cdlt.node.outputs[0].shape[2])
        OW = cdlt.dummy_op("OW1", cdlt.node.outputs[0].shape[3])
        KH = cdlt.dummy_op("KH1", cdlt.node.inputs[3].shape[2])
        KW = cdlt.dummy_op("KW1", cdlt.node.inputs[3].shape[3])

        # Add dw conv inputs
        weight = cdlt.create_operand_template("dw_conv_wgt", OP_DTYPES, [C, ONE, KH, KW], default_dtype=OP_DTYPES[2])
        bias = cdlt.create_operand_template("dw_conv_bias", OP_DTYPES, [C], default_dtype=OP_DTYPES[2])
        cdlt.add_input(weight)
        cdlt.add_input(bias)

        s = cdlt.dummy_op("s2", cdlt.node.stride0)
        pad = cdlt.dummy_op("p2", cdlt.node.pad_int0)


        # Create outputs
        out = cdlt.create_operand_template("out", OP_DTYPES, [N, C, OH, OW], default_dtype=OP_DTYPES[0])
        cdlt.set_outputs([out])

        # Create temporary storage
        clip_out1 = cdlt.create_operand_template("clip_out1", OP_DTYPES, [N, C, params['OH'], params['OW']], default_dtype=OP_DTYPES[2])
        cdlt.add_temp_operand(clip_out1)

        dw_conv_out = cdlt.create_operand_template("dw_conv_out", OP_DTYPES, [N, C, OH, OW], default_dtype=OP_DTYPES[2])
        dw_conv_out.start_location = "VMEM1"
        cdlt.add_temp_operand(dw_conv_out)


        # Setup min/max params
        minval = cdlt.dummy_op("min", cdlt.node.kwargs['minval'], dtype="FXP32")
        maxval = cdlt.dummy_op("max", cdlt.node.kwargs['maxval'], dtype="FXP32")
        SIMD_SIZE = cdlt.dummy_op("SIMD_SIZE", cdlt.hag.all_subgraph_nodes['SIMD'].dimensions[0])

        min_op = cdlt.create_temp_operand([SIMD_SIZE], "IMM")
        max_op = cdlt.create_temp_operand([SIMD_SIZE], "IMM")

        cdlt, conv_out = create_conv_func(cdlt, params)
        cdlt.configure("start", "SIMD")
        m0 = create_immediate_with_operand(cdlt, QUANT_SCALE, simd_size=SIMD_SIZE)
        nshift = create_immediate_with_operand(cdlt, SIGN_SHIFT, simd_size=SIMD_SIZE)
        zero = create_immediate_with_operand(cdlt, 0, simd_size=SIMD_SIZE)
        cdlt.configure("start", "IMM", immediate_value=minval, index=1)
        cdlt.configure("start", "IMM", immediate_value=maxval, index=2)
        with cdlt.loop(ONE) as one:
            with cdlt.loop(N) as n:
                with cdlt.loop(C) as c:
                    with cdlt.loop(OH) as y:
                        with cdlt.loop(OW) as x:
                            with cdlt.loop(KH) as kh:
                                with cdlt.loop(KW) as kw:
                                    cdlt.transfer(weight, ["DRAM", "VMEM1"])
                                    cdlt.transfer(bias, ["DRAM", "VMEM2"])
                                    # cdlt.transfer(out, ["DRAM", "VMEM1"])
                                    out.set_write_destination('VMEM1')
                                    clip_out1.set_write_destination("VMEM2")
                                    dw_conv_out.set_write_destination("VMEM1")

                                    # Scale inputs
                                    indices = (n, c, y * s + kh, x * s + kw)

                                    # First clip
                                    cdlt.compute("MAX", [conv_out[n, c, y * s + kh, x * s + kw], max_op],
                                                 [clip_out1[n, c, y * s + kh, x * s + kw]
                                                  ],
                                                 target="SIMD")

                                    cdlt.compute("MIN", [clip_out1[n, c, y * s + kh, x * s + kw], min_op],
                                                 [clip_out1[n, c, y * s + kh, x * s + kw]],
                                                 target="SIMD")


                                    # DW-Conv
                                    cdlt.compute("MOVE", [zero], [dw_conv_out[n, c ,y , x]], target="SIMD")

                                    cdlt.compute("MACC",
                                                 [clip_out1[n, c, y * s + kh, x * s + kw], weight[c, one, kh, kw],
                                                  dw_conv_out[n, c, y, x]], [dw_conv_out[n, c, y, x]],
                                                 target="SIMD")

                                    cdlt.compute("ADD", [dw_conv_out[n, c, y, x], bias[c]], [dw_conv_out[n,c,y,x]],
                                                 target="SIMD")
                                    # Scale
                                    indices = (n, c, y, x)

                                    # Second clip
                                    cdlt.compute("MAX", [dw_conv_out[n, c, y, x], max_op], [dw_conv_out[n, c, y, x]],
                                                 target="SIMD")

                                    cdlt.compute("MIN", [dw_conv_out[n, c, y, x], min_op], [out[n, c, y, x]],
                                                 target="SIMD")


                                    cdlt.transfer(out, ["VMEM1", "DRAM"])


        cdlt.configure("end", "SIMD")
    cdlt = add_conv_constraints(hag, cdlt, is_fusion=True)
    cdlt = add_simd_constraint(hag, cdlt, "OC")

    cdlt.update_compilation_param("LEVEL1_hint", "sizes['OH'] == (sizes['OH1'] - 1)*params['s2'] + sizes['KH1']")
    cdlt.update_compilation_param("LEVEL1_hint", "sizes['OW'] == (sizes['OW1'] - 1)*params['s2'] + sizes['KW1']")
    cdlt = add_simd_tile_constraint(hag, cdlt, ["KH1", "KW1"])

    # cdlt.update_compilation_param("LEVEL1_hint", "splits['KW1'] == 1")
    # cdlt.update_compilation_param("LEVEL1_hint", "splits['KH1'] == 1")

    return cdlt

def depthwise_conv_clip(hag: ArchitectureNode):
    # TODO: De-duplicate replicated outer loops for a given VMEM
    # TODO: Add zero constant
    # TODO: Replicate inner loops on a per-operand basis, and use the same offset from the previous tile
    # TODO: Make sure the output operands use 0 for it's offset
    # TODO: Need to figure out how to change the memory layout
    with CodeletTemplate("depthwise_conv_bias_clip") as cdlt:
        N = cdlt.dummy_op("N", cdlt.node.inputs[0].shape[0])
        C = cdlt.dummy_op("C", cdlt.node.inputs[0].shape[1])
        ONE = cdlt.dummy_op("ONE", cdlt.node.inputs[1].shape[1])
        KH = cdlt.dummy_op("KH", cdlt.node.inputs[1].shape[2])
        KW = cdlt.dummy_op("KW", cdlt.node.inputs[1].shape[3])
        OH = cdlt.dummy_op("OH", cdlt.node.outputs[0].shape[2])
        OW = cdlt.dummy_op("OW", cdlt.node.outputs[0].shape[3])
        IH = cdlt.dummy_op("IH", cdlt.node.inputs[0].shape[2])
        IW = cdlt.dummy_op("IW", cdlt.node.inputs[0].shape[3])

        data = cdlt.create_operand_template("data", OP_DTYPES, [N, C, IH, IW], default_dtype=OP_DTYPES[2])
        weight = cdlt.create_operand_template("weight", OP_DTYPES, [C, ONE, KH, KW], default_dtype=OP_DTYPES[2])
        bias = cdlt.create_operand_template("bias", OP_DTYPES, [C], default_dtype=OP_DTYPES[2])
        out = cdlt.create_operand_template("out", OP_DTYPES, [N, C, OH, OW], default_dtype=OP_DTYPES[2])
        cdlt.set_inputs([data, weight, bias])
        cdlt.set_outputs([out])
        # Create temporary storage
        # clip_out1 = cdlt.create_operand_template("clip_out1", OP_DTYPES, [N, C, OH, OW], default_dtype=OP_DTYPES[2])
        # cdlt.add_temp_operand(clip_out1)
        # clip_out1.start_location = "VMEM2"


        stride = cdlt.dummy_op("stride", cdlt.node.stride)
        pad = cdlt.dummy_op("pad", cdlt.node.pad_int)

        minval = cdlt.dummy_op("min", cdlt.node.kwargs['minval'], dtype="FXP32")
        maxval = cdlt.dummy_op("max", cdlt.node.kwargs['maxval'], dtype="FXP32")
        SIMD_SIZE = cdlt.dummy_op("SIMD_SIZE", cdlt.hag.all_subgraph_nodes['SIMD'].dimensions[0])

        min_op = cdlt.create_temp_operand([SIMD_SIZE], "IMM")
        max_op = cdlt.create_temp_operand([SIMD_SIZE], "IMM")
        # OS ->
        cdlt.configure("start", "SIMD")
        m0 = create_immediate_with_operand(cdlt, QUANT_SCALE, simd_size=SIMD_SIZE)
        nshift = create_immediate_with_operand(cdlt, SIGN_SHIFT, simd_size=SIMD_SIZE)
        cdlt.configure("start", "IMM", immediate_value=0, index=0)
        cdlt.configure("start", "IMM", immediate_value=minval, index=len(cdlt.temps))
        cdlt.configure("start", "IMM", immediate_value=maxval, index=len(cdlt.temps)+1)
        with cdlt.loop(ONE) as one:
            with cdlt.loop(N) as n:
                with cdlt.loop(C) as c:
                    with cdlt.loop(OH) as y:
                        with cdlt.loop(OW) as x:
                            with cdlt.loop(KH) as kh:
                                with cdlt.loop(KW) as kw:
                                    cdlt.transfer(weight, ["DRAM", "VMEM1"])
                                    cdlt.transfer(data, ["DRAM", "VMEM2"])
                                    cdlt.transfer(bias, ["DRAM", "VMEM1"])
                                    cdlt.transfer(out, ["DRAM", "VMEM1"])
                                    out.set_write_destination("VMEM1")

                                    cdlt.compute("MACC", [data[n, c, y * stride + kh, x * stride + kw], weight[c, one, kh, kw], out[n, c, y, x]], [out[n, c, y, x]], target="SIMD")
                                    cdlt.compute("ADD", [out[n, c, y, x], bias[c]], [out[n,c,y,x]], target="SIMD")
                                    indices = (n, c, y, x)
                                    cdlt.compute("MAX", [out[n, c, y, x], max_op],
                                                 [out[n, c, y, x]
                                                  ],
                                                 target="SIMD")
                                    cdlt.compute("MIN", [out[n, c, y, x], min_op],
                                                 [out[n, c, y, x]
                                                  ],
                                                 target="SIMD")

                                    cdlt.transfer(out, ["VMEM1", "DRAM"])

        cdlt.configure("end", "SIMD")
    cdlt = add_simd_constraint(hag, cdlt, "C")
    cdlt = add_simd_tile_constraint(hag, cdlt, ["KH", "KW"])
    return cdlt

def conv_clip(hag: ArchitectureNode):
    with CodeletTemplate("conv_bias_clip") as cdlt:

        cdlt, params = create_conv_args(cdlt)
        # Setup min/max params
        minval = cdlt.dummy_op("min", cdlt.node.kwargs['minval'], dtype="FXP32")
        maxval = cdlt.dummy_op("max", cdlt.node.kwargs['maxval'], dtype="FXP32")
        SIMD_SIZE = cdlt.dummy_op("SIMD_SIZE", cdlt.hag.all_subgraph_nodes['SIMD'].dimensions[0])

        min_op = cdlt.create_temp_operand([SIMD_SIZE], "IMM")
        max_op = cdlt.create_temp_operand([SIMD_SIZE], "IMM")


        cdlt, conv_out = create_conv_func(cdlt, params)

        OC, N, OH, OW = params['OC'], params['N'], params['OH'], params['OW']
        # clip_out = cdlt.create_operand_template("clip_out", OP_DTYPES, [N, OC, OH, OW], default_dtype=OP_DTYPES[2])
        # clip_out.start_location = "VMEM1"
        # cdlt.add_temp_operand(clip_out)

        out = cdlt.create_operand_template("out", OP_DTYPES, [N, OC, OH, OW], default_dtype=OP_DTYPES[0])
        cdlt.set_outputs([out])

        cdlt.configure("start", "SIMD")
        m0 = create_immediate_with_operand(cdlt, QUANT_SCALE, simd_size=SIMD_SIZE)
        nshift = create_immediate_with_operand(cdlt, SIGN_SHIFT, simd_size=SIMD_SIZE)
        cdlt.configure("start", "IMM", immediate_value=16, index=0)
        cdlt.configure("start", "IMM", immediate_value=minval, index=len(cdlt.temps) + 1)
        cdlt.configure("start", "IMM", immediate_value=maxval, index=len(cdlt.temps) + 2)
        with cdlt.loop(OC) as oc:
            with cdlt.loop(N) as n:
                with cdlt.loop(OH) as y:
                    with cdlt.loop(OW) as x:
                        out.set_write_destination("VMEM2")
                        indices = (n, oc, y, x)
                        cdlt.compute("MAX", [conv_out[n,oc, y, x], max_op],
                                     [out[n,oc, y, x]
                                      ],
                                     target="SIMD")
                        cdlt.compute("MIN", [out[n,oc, y, x], min_op],
                                     [out[n,oc, y, x]
                                      ],
                                     target="SIMD")
                        cdlt.transfer(out, ["VMEM2", "DRAM"])
        cdlt.configure("end", "SIMD")

    cdlt = add_conv_constraints(hag, cdlt, is_fusion=True)
    cdlt = add_simd_constraint(hag, cdlt, "OC")

    return cdlt

def inv_sqrt(hag: ArchitectureNode):
    with CodeletTemplate("sqrt_reciprocal") as cdlt:
        N = cdlt.dummy_op("N", cdlt.node.inputs[0].shape[0])
        C = cdlt.dummy_op("C", cdlt.node.inputs[0].shape[1])
        H = cdlt.dummy_op("H", cdlt.node.inputs[0].shape[2])
        W = cdlt.dummy_op("W", cdlt.node.inputs[0].shape[3])
        data = cdlt.create_operand_template("data", OP_DTYPES, [N, C, H, W], default_dtype=OP_DTYPES[2])
        out = cdlt.create_operand_template("out", OP_DTYPES, [N, C, H, W], default_dtype=OP_DTYPES[2])
        cdlt.set_inputs([data])
        cdlt.set_outputs([out])

        cdlt.configure("start", "SIMD")
        with cdlt.loop(C) as c:
            with cdlt.loop(N) as n:
                with cdlt.loop(H) as h:
                    with cdlt.loop(W) as w:
                        cdlt.transfer(data, ["DRAM", "VMEM1"])
                        out.set_write_destination('VMEM1')
                        cdlt.compute('INV_SQRT', [data[n, c, h, w]], [out[n, c, h, w]], target='SIMD')
                        cdlt.transfer(out, ['VMEM1', 'DRAM'])
        cdlt.configure("end", "SIMD")
    cdlt = add_simd_constraint(hag, cdlt, "C")
    return cdlt

def add_add(hag):
    with CodeletTemplate('add_add') as cdlt:
        N = cdlt.dummy_op("N", cdlt.node.inputs[0].shape[0])
        C = cdlt.dummy_op("C", cdlt.node.inputs[0].shape[1])
        H = cdlt.dummy_op("H", cdlt.node.inputs[0].shape[2])
        op1 = cdlt.create_operand_template("op1", OP_DTYPES, [N, C, H], default_dtype=OP_DTYPES[2])
        op2 = cdlt.create_operand_template("op2", OP_DTYPES, [N, C, H], default_dtype=OP_DTYPES[2])
        op3 = cdlt.create_operand_template("op3", OP_DTYPES, [N, C, H], default_dtype=OP_DTYPES[2])
        out = cdlt.create_operand_template("out", OP_DTYPES, [N, C, H], default_dtype=OP_DTYPES[2])
        cdlt.set_inputs([op1, op2, op3])
        cdlt.set_outputs([out])
        simd_size = cdlt.dummy_op("SIMD_SIZE", cdlt.hag.all_subgraph_nodes['SIMD'].dimensions[0])
        cdlt.configure('start', 'SIMD')
        m0 = create_immediate_with_operand(cdlt, QUANT_SCALE, simd_size=simd_size)
        nshift = create_immediate_with_operand(cdlt, SIGN_SHIFT, simd_size=simd_size)
        with cdlt.loop(N) as n:
            with cdlt.loop(C) as c:
                with cdlt.loop(H) as h:
                    cdlt.transfer(op1, ["DRAM", "VMEM1"])
                    cdlt.transfer(op2, ["DRAM", "VMEM2"])
                    cdlt.transfer(op3, ["DRAM", "VMEM2"])
                    out.set_write_destination("VMEM1")
                    indices = (n,c,h)
                    cdlt.compute("ADD", [op1[n, c, h], op2[n, c, h]], [out[n, c, h]], target="SIMD")
                    cdlt.compute("ADD", [out[n, c, h], op3[n, c, h]], [out[n, c, h]], target="SIMD")
                    cdlt.transfer(out, ["VMEM1", "DRAM"])
        cdlt.configure("end", "SIMD")
    cdlt = add_simd_constraint(hag, cdlt, "C")
    return cdlt

def add_add4d(hag):
    with CodeletTemplate('add_add4d') as cdlt:
        N = cdlt.dummy_op("N", cdlt.node.inputs[0].shape[0])
        C = cdlt.dummy_op("C", cdlt.node.inputs[0].shape[1])
        H = cdlt.dummy_op("H", cdlt.node.inputs[0].shape[2])
        W = cdlt.dummy_op("W", cdlt.node.inputs[0].shape[3])
        op1 = cdlt.create_operand_template("op1", OP_DTYPES, [N, C, H, W], default_dtype=OP_DTYPES[2])
        op2 = cdlt.create_operand_template("op2", OP_DTYPES, [N, C, H, W], default_dtype=OP_DTYPES[2])
        op3 = cdlt.create_operand_template("op3", OP_DTYPES, [N, C, H, W], default_dtype=OP_DTYPES[2])
        out = cdlt.create_operand_template("out", OP_DTYPES, [N, C, H, W], default_dtype=OP_DTYPES[2])
        cdlt.set_inputs([op1, op2, op3])
        cdlt.set_outputs([out])
        simd_size = cdlt.dummy_op("SIMD_SIZE", cdlt.hag.all_subgraph_nodes['SIMD'].dimensions[0])
        cdlt.configure('start', 'SIMD')
        m0 = create_immediate_with_operand(cdlt, QUANT_SCALE, simd_size=simd_size)
        nshift = create_immediate_with_operand(cdlt, SIGN_SHIFT, simd_size=simd_size)
        with cdlt.loop(N) as n:
            with cdlt.loop(C) as c:
                with cdlt.loop(H) as h:
                    with cdlt.loop(W) as w:
                        cdlt.transfer(op1, ["DRAM", "VMEM1"])
                        cdlt.transfer(op2, ["DRAM", "VMEM2"])
                        cdlt.transfer(op3, ["DRAM", "VMEM2"])
                        out.set_write_destination("VMEM1")
                        indices = (n,c,h, w)
                        cdlt.compute("ADD", [op1[indices], op2[indices]], [out[indices]], target="SIMD")
                        cdlt.compute("ADD", [out[indices], op3[indices]], [out[indices]], target="SIMD")
                        cdlt.transfer(out, ["VMEM1", "DRAM"])
        cdlt.configure("end", "SIMD")
    cdlt = add_simd_constraint(hag, cdlt, "C")
    return cdlt

def mul_add(hag):
    with CodeletTemplate('mul_add') as cdlt:
        N = cdlt.dummy_op("N", cdlt.node.inputs[0].shape[0])
        C = cdlt.dummy_op("C", cdlt.node.inputs[0].shape[1])
        H = cdlt.dummy_op("H", cdlt.node.inputs[0].shape[2])
        op1 = cdlt.create_operand_template("op1", OP_DTYPES, [N, C, H], default_dtype=OP_DTYPES[2])
        op2 = cdlt.create_operand_template("op2", OP_DTYPES, [H], default_dtype=OP_DTYPES[2])
        op3 = cdlt.create_operand_template("op3", OP_DTYPES, [H], default_dtype=OP_DTYPES[2])
        out = cdlt.create_operand_template("out", OP_DTYPES, [N, C, H], default_dtype=OP_DTYPES[2])
        cdlt.set_inputs([op1, op2, op3])
        cdlt.set_outputs([out])
        simd_size = cdlt.dummy_op("SIMD_SIZE", cdlt.hag.all_subgraph_nodes['SIMD'].dimensions[0])
        cdlt.configure('start', 'SIMD')
        m0 = create_immediate_with_operand(cdlt, QUANT_SCALE, simd_size=simd_size)
        nshift = create_immediate_with_operand(cdlt, SIGN_SHIFT, simd_size=simd_size)
        with cdlt.loop(N) as n:
            with cdlt.loop(C) as c:
                with cdlt.loop(H) as h:
                    cdlt.transfer(op1, ["DRAM", "VMEM2"])
                    cdlt.transfer(op2, ["DRAM", "VMEM1"])
                    cdlt.transfer(op3, ["DRAM", "VMEM1"])
                    op1.set_write_destination("VMEM2")
                    out.set_write_destination("VMEM1")
                    indices = (n,c,h)
                    cdlt.compute("MUL", [op1[n, c, h], op2[h]], [op1[n, c, h]], target="SIMD")
                    cdlt.compute("ADD", [op1[n, c, h], op3[h]], [out[n, c, h]], target="SIMD")
                    cdlt.transfer(out, ["VMEM1", "DRAM"])
        cdlt.configure("end", "SIMD")

    cdlt = add_simd_constraint(hag, cdlt, "H")
    return cdlt

def sub_mul(hag):
    with CodeletTemplate('sub_mul') as cdlt:
        N = cdlt.dummy_op("N", cdlt.node.inputs[0].shape[0])
        C = cdlt.dummy_op("C", cdlt.node.inputs[0].shape[1])
        H = cdlt.dummy_op("H", cdlt.node.inputs[0].shape[2])
        W = cdlt.dummy_op("W", cdlt.node.inputs[0].shape[3])
        op1 = cdlt.create_operand_template("op1", OP_DTYPES, [N, C, H, W], default_dtype=OP_DTYPES[2])
        out = cdlt.create_operand_template("out", OP_DTYPES, [N, C, H, W], default_dtype=OP_DTYPES[2])
        cdlt.set_inputs([op1])
        cdlt.set_outputs([out])

        mul_rhs = cdlt.dummy_op("mul_rhs", cdlt.node.mul_rhs, dtype="FXP32")
        sub_rhs = cdlt.dummy_op("sub_rhs", cdlt.node.sub_rhs, dtype="FXP32")
        SIMD_SIZE = cdlt.dummy_op("SIMD_SIZE", cdlt.hag.all_subgraph_nodes['SIMD'].dimensions[0])

        mul_op = cdlt.create_temp_operand([SIMD_SIZE], "IMM")
        sub_op = cdlt.create_temp_operand([SIMD_SIZE], "IMM")
        cdlt.configure("start", "SIMD")
        cdlt.configure("start", "IMM", immediate_value=mul_rhs, index=len(cdlt.temps))
        cdlt.configure("start", "IMM", immediate_value=sub_rhs, index=len(cdlt.temps) + 1)
        with cdlt.loop(N) as n:
            with cdlt.loop(C) as c:
                with cdlt.loop(H) as h:
                    with cdlt.loop(W) as w:
                        cdlt.transfer(op1, ["DRAM", "VMEM1"])
                        out.set_write_destination("VMEM1")
                        cdlt.compute("SUB", [op1[n, c, h, w], sub_op], [out[n, c, h, w]], target="SIMD")
                        cdlt.compute("MUL", [out[n, c, h, w], mul_op], [out[n, c, h, w]], target="SIMD")
                        cdlt.transfer(out, ["VMEM1", "DRAM"])
        cdlt.configure("end", "SIMD")

    cdlt = add_simd_constraint(hag, cdlt, "W")
    return cdlt

def sub_pow(hag):
    with CodeletTemplate('sub_pow') as cdlt:
        N = cdlt.dummy_op("N", cdlt.node.inputs[0].shape[0])
        C = cdlt.dummy_op("C", cdlt.node.inputs[0].shape[1])
        H = cdlt.dummy_op("H", cdlt.node.inputs[0].shape[2])
        op1 = cdlt.create_operand_template("op1", OP_DTYPES, [N, C, H], default_dtype=OP_DTYPES[2])
        op2 = cdlt.create_operand_template("op2", OP_DTYPES, [N, C, H], default_dtype=OP_DTYPES[2])


        exp = cdlt.dummy_op("exp", cdlt.node.kwargs['exp'], dtype="FXP32")
        SIMD_SIZE = cdlt.dummy_op("SIMD_SIZE", cdlt.hag.all_subgraph_nodes['SIMD'].dimensions[0])
        out = cdlt.create_operand_template("out", OP_DTYPES, [N, C, H], default_dtype=OP_DTYPES[2])
        cdlt.set_inputs([op1, op2])
        cdlt.set_outputs([out])
        cdlt.configure("start", "SIMD")
        cdlt.configure("start", "IMM", immediate_value=0, index=0)
        with cdlt.loop(N) as n:
            with cdlt.loop(C) as c:
                with cdlt.loop(H) as h:
                    cdlt.transfer(op1, ["DRAM", "VMEM1"])
                    cdlt.transfer(op2, ["DRAM", "VMEM2"])
                    out.set_write_destination("VMEM2")
                    op1.set_write_destination("VMEM1")
                    cdlt.compute("SUB", [op1[n, c, h], op2[n, c, h]], [op1[n, c, h]], target="SIMD")
                    cdlt.compute("MOVE", [op1[n, c, h]], [out[n, c, h]], target="SIMD")
                    cdlt.compute("MUL", [op1[n, c, h], out[n, c, h]], [out[n, c, h]], target="SIMD")
                    cdlt.transfer(out, ["VMEM2", "DRAM"])
        cdlt.configure("end", "SIMD")
    cdlt = add_simd_constraint(hag, cdlt, "C")
    return cdlt

def add_sqrt_div(hag):
    with CodeletTemplate('add_sqrt_div') as cdlt:
        N = cdlt.dummy_op("N", cdlt.node.inputs[0].shape[0])
        C = cdlt.dummy_op("C", cdlt.node.inputs[0].shape[1])
        H = cdlt.dummy_op("H", cdlt.node.inputs[0].shape[2])
        op1 = cdlt.create_operand_template("op1", OP_DTYPES, [N, C, H], default_dtype=OP_DTYPES[2])
        # op2 = cdlt.create_operand_template("op2", OP_DTYPES, [N], default_dtype=OP_DTYPES[2])
        op3 = cdlt.create_operand_template("op3", OP_DTYPES, [N, C, H], default_dtype=OP_DTYPES[2])
        out = cdlt.create_operand_template("out", OP_DTYPES, [N, C, H], default_dtype=OP_DTYPES[2])
        cdlt.set_inputs([op1, op3])
        cdlt.set_outputs([out])

        x = cdlt.create_operand_template("x", OP_DTYPES, [N, C, H], default_dtype=OP_DTYPES[2])
        cdlt.add_temp_operand(x)

        y = cdlt.create_operand_template("y", OP_DTYPES, [N, C, H], default_dtype=OP_DTYPES[2])
        cdlt.add_temp_operand(y)

        add_lhs = cdlt.dummy_op("add_lhs", cdlt.node.kwargs['add_lhs'], dtype="FXP32")
        SIMD_SIZE = cdlt.dummy_op("SIMD_SIZE", cdlt.hag.all_subgraph_nodes['SIMD'].dimensions[0])

        add_op = cdlt.create_temp_operand([SIMD_SIZE], "IMM")
        cdlt.configure("start", "SIMD")
        cdlt.configure("start", "IMM", immediate_value=add_lhs, index=len(cdlt.temps))
        t = create_immediate_with_operand(cdlt, 2**16, simd_size=SIMD_SIZE)
        one = create_immediate_with_operand(cdlt, 1, simd_size=SIMD_SIZE)
        m0 = create_immediate_with_operand(cdlt, QUANT_SCALE, simd_size=SIMD_SIZE)
        nshift = create_immediate_with_operand(cdlt, SIGN_SHIFT, simd_size=SIMD_SIZE)
        with cdlt.loop(H) as h:
            with cdlt.loop(N) as n:
                with cdlt.loop(C) as c:
                    cdlt.transfer(op1, ["DRAM", "VMEM1"])
                    cdlt.transfer(op3, ["DRAM", "VMEM1"])
                    out.set_write_destination("VMEM2")
                    x.set_write_destination("VMEM1")
                    y.set_write_destination("VMEM1")

                    # ADD
                    cdlt.compute("ADD", [op1[n, c, h], add_op], [x[n, c, h]], target="SIMD")

                    # SQRT
                    cdlt.compute("MUL", [x[n, c, h], t], [y[n, c, h]], target="SIMD")
                    cdlt.compute("CEIL", [y[n, c, h]], [y[n, c, h]], target="SIMD")
                    cdlt.compute("RSHIFT", [y[n, c, h], one], [y[n, c, h]], target="SIMD")
                    cdlt.compute("ADD", [y[n, c, h], t], [out[n, c, h]], target="SIMD")

                    cdlt.compute("MUL", [x[n, c, h], t], [y[n, c, h]], target="SIMD")
                    cdlt.compute("CEIL", [y[n, c, h]], [y[n, c, h]], target="SIMD")
                    cdlt.compute("RSHIFT", [y[n, c, h], one], [y[n, c, h]], target="SIMD")
                    cdlt.compute("ADD", [y[n, c, h], t], [out[n, c, h]], target="SIMD")

                    cdlt.compute("MUL", [x[n, c, h], t], [y[n, c, h]], target="SIMD")
                    cdlt.compute("CEIL", [y[n, c, h]], [y[n, c, h]], target="SIMD")
                    cdlt.compute("RSHIFT", [y[n, c, h], one], [y[n, c, h]], target="SIMD")
                    cdlt.compute("ADD", [y[n, c, h], t], [out[n, c, h]], target="SIMD")

                    cdlt.compute("MUL", [x[n, c, h], t], [y[n, c, h]], target="SIMD")
                    cdlt.compute("CEIL", [y[n, c, h]], [y[n, c, h]], target="SIMD")
                    cdlt.compute("RSHIFT", [y[n, c, h], one], [y[n, c, h]], target="SIMD")
                    cdlt.compute("ADD", [y[n, c, h], t], [out[n, c, h]], target="SIMD")

                    ## Div
                    indices = (n, c, h)

                    cdlt.compute("MUL", [out[n, c, h], op3[n, c, h]], [out[n, c, h]], target="SIMD")

                    cdlt.transfer(out, ["VMEM1", "DRAM"])
        cdlt.configure("end", "SIMD")

    cdlt = add_simd_constraint(hag, cdlt, "H")
    return cdlt

def matmul_add(hag):
    with CodeletTemplate('matmul_add') as cdlt:
        B = cdlt.dummy_op("B", cdlt.node.inputs[0].shape[0])
        M = cdlt.dummy_op("M", cdlt.node.inputs[0].shape[1])
        N = cdlt.dummy_op("N", cdlt.node.inputs[0].shape[2])
        P = cdlt.dummy_op("P", cdlt.node.inputs[1].shape[1])


        data = cdlt.create_operand_template("data", OP_DTYPES, [B, M, N], default_dtype=OP_DTYPES[0])
        weight = cdlt.create_operand_template("weight", OP_DTYPES, [N, P], default_dtype=OP_DTYPES[0])
        bias = cdlt.create_operand_template("bias", OP_DTYPES, [P], default_dtype=OP_DTYPES[2])
        cdlt.set_inputs([data, weight, bias])
        data = cdlt.inputs[0]
        weight = cdlt.inputs[1]
        bias = cdlt.inputs[2]

        gemm_out = cdlt.create_operand_template("gemm_out", OP_DTYPES, [B, M, P], default_dtype=OP_DTYPES[2])
        cdlt.set_outputs([gemm_out])

        cdlt.configure("start", "systolic_array")
        cdlt.configure("start", "WBUF")
        cdlt.configure("start", "IBUF")
        cdlt.configure("start", "OBUF")
        cdlt.configure("start", "BBUF")
        with cdlt.loop(B) as b:
            with cdlt.loop(M) as m:
                with cdlt.loop(N) as n:
                    with cdlt.loop(P) as p:
                        cdlt.transfer(data, ["DRAM", "IBUF"])
                        cdlt.transfer(weight, ["DRAM", "WBUF"])
                        cdlt.transfer(bias, ["DRAM", "BBUF"])
                        cdlt.transfer(gemm_out, ["DRAM", "OBUF"])
                        gemm_out.set_write_destination("OBUF")
                        cdlt.compute("MVMUL", [data[b, m, n], weight[n, p], bias[p], gemm_out[b, m, p]],
                                     [gemm_out[b, m, p]], target="pe_array")
                        cdlt.transfer(gemm_out, ["OBUF", "DRAM"])

        # TODO: Add store off chip
        cdlt.configure("end", "WBUF")
        cdlt.configure("end", "IBUF")
        cdlt.configure("end", "OBUF")
        cdlt.configure("end", "BBUF")
        cdlt.configure("end", "systolic_array")
    cdlt = add_gemm_constraints(hag, cdlt)
    return cdlt

def matmul_add_add(hag):
    with CodeletTemplate('matmul_add_add') as cdlt:
        cdlt, params = create_matmul3d_args(cdlt)
        B, M, P = params['B'], params['M'], params['P']

        add_lhs = cdlt.create_operand_template("add_lhs", OP_DTYPES, [B, M, P], default_dtype=OP_DTYPES[2])
        cdlt.add_input(add_lhs)

        cdlt, gemm_out = create_mamtul3d_func(cdlt, params)
        out = cdlt.create_operand_template("out", OP_DTYPES, [B, M, P], default_dtype=OP_DTYPES[0])
        cdlt.set_outputs([out])

        simd_size = cdlt.dummy_op("SIMD_SIZE", cdlt.hag.all_subgraph_nodes['SIMD'].dimensions[0])
        cdlt.configure('start', 'SIMD')
        m0 = create_immediate_with_operand(cdlt, QUANT_SCALE, simd_size=simd_size)
        nshift = create_immediate_with_operand(cdlt, SIGN_SHIFT, simd_size=simd_size)
        with cdlt.loop(P) as p:
            with cdlt.loop(B) as b:
                with cdlt.loop(M) as m:
                    cdlt.transfer(add_lhs, ["DRAM", "VMEM2"])
                    out.set_write_destination('VMEM1')
                    add_lhs.set_write_destination("VMEM2")
                    indices = (b, m, p)
                    add_scale_op(cdlt, add_lhs, add_lhs, m0, nshift, indices)
                    cdlt.compute("ADD", [gemm_out[indices], add_lhs[indices]], [out[indices]],
                                 target="SIMD")
                    cdlt.transfer(out, ["VMEM1", "DRAM"])
        cdlt.configure('end', 'SIMD')
    cdlt = add_gemm_constraints(hag, cdlt)
    return cdlt

def matmul_add_gelu(hag):
    with CodeletTemplate('matmul_add_gelu') as cdlt:
        cdlt, params = create_matmul3d_args(cdlt)
        B, M, P = params['B'], params['M'], params['P']

        cdlt, gemm_out = create_mamtul3d_func(cdlt, params)
        out = cdlt.create_operand_template("out", OP_DTYPES, [B, M, P], default_dtype=OP_DTYPES[0])
        cdlt.set_outputs([out])
        gelu_out = cdlt.create_operand_template("gelu_out", OP_DTYPES, [B, M, P], default_dtype=OP_DTYPES[2])
        gelu_out.start_location = "VMEM2"
        cdlt.add_temp_operand(gelu_out)

        sign_val = cdlt.create_operand_template("sign_val", OP_DTYPES, [B, M, P], default_dtype=OP_DTYPES[2])
        # sign_val.start_location = "VMEM2"
        cdlt.add_temp_operand(sign_val)

        simd_size = cdlt.dummy_op("SIMD_SIZE", cdlt.hag.all_subgraph_nodes['SIMD'].dimensions[0])
        cdlt.configure('start', 'SIMD')
        b_s = create_immediate_with_operand(cdlt, -1.769/QUANT_SCALE, simd_size=simd_size, cast_float_to_fxp=True)
        aop = create_immediate_with_operand(cdlt, -0.2888, simd_size=simd_size, cast_float_to_fxp=True)
        bop = create_immediate_with_operand(cdlt, -1.769, simd_size=simd_size, cast_float_to_fxp=True)
        cop = create_immediate_with_operand(cdlt, 1, simd_size=simd_size)
        s_f = create_immediate_with_operand(cdlt, QUANT_SCALE, simd_size=simd_size)
        m0 = create_immediate_with_operand(cdlt, QUANT_SCALE, simd_size=simd_size)
        nshift = create_immediate_with_operand(cdlt, SIGN_SHIFT, simd_size=simd_size)
        with cdlt.loop(P) as p:
            with cdlt.loop(B) as b:
                with cdlt.loop(M) as m:
                    out.set_write_destination('VMEM1')
                    gelu_out.set_write_destination("VMEM2")
                    sign_val.set_write_destination("VMEM1")
                    indices = (b, m, p)

                    cdlt.compute("ABS", [gemm_out[indices]], [gelu_out[indices]],
                                 target="SIMD")
                    cdlt.compute("MIN", [gelu_out[indices], b_s], [gelu_out[indices]],
                                 target="SIMD")
                    cdlt.compute("ADD", [gelu_out[indices], bop], [gelu_out[indices]],
                                 target="SIMD")
                    cdlt.compute("MOVE", [gelu_out[indices]], [sign_val[indices]],
                                 target="SIMD")

                    cdlt.compute("MUL", [gelu_out[indices], sign_val[indices]], [gelu_out[indices]],
                                 target="SIMD")
                    # add_scale_and_cast_op(cdlt, add_lhs, out, m0, nshift, indices)
                    cdlt.compute("MUL", [gelu_out[indices], aop], [gelu_out[indices]],
                                 target="SIMD")
                    cdlt.compute("ADD", [gelu_out[indices], cop], [gelu_out[indices]],
                                 target="SIMD")
                    cdlt.compute("SIGN", [gemm_out[indices]], [sign_val[indices]],
                                 target="SIMD")

                    cdlt.compute("MUL", [gelu_out[indices], sign_val[indices]], [gelu_out[indices]],
                                 target="SIMD")
                    cdlt.compute("ADD", [gelu_out[indices], m0], [gelu_out[indices]], target="SIMD")
                    cdlt.compute("MUL", [gemm_out[indices], gelu_out[indices]], [out[indices]], target="SIMD")
                    cdlt.compute("MUL", [out[indices], s_f], [out[indices]], target="SIMD")

                    cdlt.transfer(out, ["VMEM1", "DRAM"])
        cdlt.configure('end', 'SIMD')
    cdlt = add_gemm_constraints(hag, cdlt)
    return cdlt

def matmul_div_add(hag):
    with CodeletTemplate('matmul_div_add') as cdlt:
        cdlt, params = create_matmul4d_args(cdlt)
        B, M, P, C, N = params['B'], params['M'], params['P'], params['C'], params['N']

        add_lhs = cdlt.create_operand_template("add_lhs", OP_DTYPES, [B, C, M, P], default_dtype=OP_DTYPES[2])
        cdlt.add_input(add_lhs)

        cdlt, gemm_out = create_mamtul4d_func(cdlt, params)
        out = cdlt.create_operand_template("out", OP_DTYPES, [B, C, M, P], default_dtype=OP_DTYPES[0])
        cdlt.set_outputs([out])
        add_out = cdlt.create_operand_template("add_out", OP_DTYPES, [B, C, M, P], default_dtype=OP_DTYPES[2])
        add_out.start_location = "VMEM2"
        cdlt.add_temp_operand(add_out)

        mul_rhs = cdlt.dummy_op("mul_rhs", cdlt.node.div_lhs, dtype="FXP32")
        simd_size = cdlt.dummy_op("SIMD_SIZE", cdlt.hag.all_subgraph_nodes['SIMD'].dimensions[0])

        mul_op = cdlt.create_temp_operand([simd_size], "IMM")

        cdlt.configure('start', 'SIMD')
        cdlt.configure("start", "IMM", immediate_value=mul_rhs, index=len(cdlt.temps))
        m0 = create_immediate_with_operand(cdlt, QUANT_SCALE, simd_size=simd_size)
        nshift = create_immediate_with_operand(cdlt, SIGN_SHIFT, simd_size=simd_size)
        with cdlt.loop(P) as p:
            with cdlt.loop(C) as c:
                with cdlt.loop(B) as b:
                    with cdlt.loop(M) as m:
                        cdlt.transfer(add_lhs, ["DRAM", "VMEM2"])
                        out.set_write_destination('VMEM1')
                        add_lhs.set_write_destination("VMEM1")
                        add_out.set_write_destination("VMEM2")
                        indices = (b ,c, m, p)
                        cdlt.compute("MUL", [gemm_out[indices], mul_op], [add_out[indices]],
                                     target="SIMD")
                        cdlt.compute("ADD", [add_out[indices], add_lhs[indices]], [out[indices]],
                                     target="SIMD")
                        cdlt.transfer(out, ["VMEM1", "DRAM"])
        cdlt.configure('end', 'SIMD')
    cdlt = add_gemm_constraints(hag, cdlt)
    return cdlt

### SW PIPELINE FUSIONS

def div_add(hag):
    with CodeletTemplate('div_add') as cdlt:
        B = cdlt.dummy_op("B", cdlt.node.inputs[0].shape[0])
        C = cdlt.dummy_op("C", cdlt.node.inputs[0].shape[1])
        M = cdlt.dummy_op("M", cdlt.node.inputs[0].shape[2])
        P = cdlt.dummy_op("P", cdlt.node.inputs[0].shape[3])
        op1 = cdlt.create_operand_template("op1", OP_DTYPES, [B,C,M,P], default_dtype=OP_DTYPES[2])
        op3 = cdlt.create_operand_template("op3", OP_DTYPES, [B,C,M,P], default_dtype=OP_DTYPES[2])
        out = cdlt.create_operand_template("out", OP_DTYPES, [B,C,M,P], default_dtype=OP_DTYPES[2])
        cdlt.set_inputs([op1, op3])
        cdlt.set_outputs([out])

        mul_rhs = cdlt.dummy_op("mul_rhs", cdlt.node.div_lhs, dtype="FXP32")
        simd_size = cdlt.dummy_op("SIMD_SIZE", cdlt.hag.all_subgraph_nodes['SIMD'].dimensions[0])

        mul_op = cdlt.create_temp_operand([simd_size], "IMM")

        cdlt.configure('start', 'SIMD')
        cdlt.configure("start", "IMM", immediate_value=mul_rhs, index=len(cdlt.temps))
        m0 = create_immediate_with_operand(cdlt, QUANT_SCALE, simd_size=simd_size)
        nshift = create_immediate_with_operand(cdlt, SIGN_SHIFT, simd_size=simd_size)
        with cdlt.loop(P) as p:
            with cdlt.loop(C) as c:
                with cdlt.loop(B) as b:
                    with cdlt.loop(M) as m:
                        cdlt.transfer(op1, ["DRAM", "VMEM2"])
                        cdlt.transfer(op3, ["DRAM", "VMEM2"])
                        out.set_write_destination('VMEM1')

                        indices = (b, c, m, p)
                        cdlt.compute("MUL", [op1[indices], mul_op], [out[indices]],
                                     target="SIMD")
                        cdlt.compute("ADD", [out[indices], op3[indices]], [out[indices]],
                                     target="SIMD")
                        cdlt.transfer(out, ["VMEM1", "DRAM"])
        cdlt.configure('end', 'SIMD')
    cdlt = add_simd_constraint(hag, cdlt, "P")
    return cdlt

def add_relu(hag):
    with CodeletTemplate('add_relu') as cdlt:
        N = cdlt.dummy_op("N", cdlt.node.inputs[0].shape[0])
        C = cdlt.dummy_op("C", cdlt.node.inputs[0].shape[1])
        H = cdlt.dummy_op("H", cdlt.node.inputs[0].shape[2])
        W = cdlt.dummy_op("W", cdlt.node.inputs[0].shape[3])
        op1 = cdlt.create_operand_template("op1", OP_DTYPES, [N, C, H, W], default_dtype=OP_DTYPES[2])
        op2 = cdlt.create_operand_template("op3", OP_DTYPES, [N, C, H, W], default_dtype=OP_DTYPES[2])
        out = cdlt.create_operand_template("out", OP_DTYPES, [N, C, H, W], default_dtype=OP_DTYPES[2])
        cdlt.set_inputs([op1, op2])
        cdlt.set_outputs([out])
        SIMD_SIZE = cdlt.dummy_op("SIMD_SIZE", cdlt.hag.all_subgraph_nodes['SIMD'].dimensions[0])
        param = cdlt.create_temp_operand([SIMD_SIZE], "IMM")



        cdlt.configure('start', 'SIMD')
        m0 = create_immediate_with_operand(cdlt, QUANT_SCALE, simd_size=SIMD_SIZE)
        nshift = create_immediate_with_operand(cdlt, SIGN_SHIFT, simd_size=SIMD_SIZE)
        cdlt.configure("start", "IMM", immediate_value=16, index=0)

        with cdlt.loop(C) as c:
            with cdlt.loop(N) as n:
                with cdlt.loop(H) as h:
                    with cdlt.loop(W) as w:
                        cdlt.transfer(op1, ["DRAM", "VMEM2"])
                        cdlt.transfer(op2, ["DRAM", "VMEM1"])
                        indices = (n,c,h,w)
                        out.set_write_destination('VMEM1')
                        op1.set_write_destination("VMEM2")
                        op2.set_write_destination("VMEM1")

                        cdlt.compute("ADD", [op1[indices], op2[indices]], [op1[indices]],
                                     target="SIMD")

                        cdlt.compute("RELU", [op1[indices], param], [out[indices]],
                                     target="SIMD")

                        cdlt.transfer(out, ["VMEM1", "DRAM"])
        cdlt.configure('end', 'SIMD')
    cdlt = add_simd_constraint(hag, cdlt, "C")
    return cdlt

def add_leaky_relu(hag):
    with CodeletTemplate('add_leaky_relu') as cdlt:
        N = cdlt.dummy_op("N", cdlt.node.inputs[0].shape[0])
        C = cdlt.dummy_op("C", cdlt.node.inputs[0].shape[1])
        H = cdlt.dummy_op("H", cdlt.node.inputs[0].shape[2])
        W = cdlt.dummy_op("W", cdlt.node.inputs[0].shape[3])
        op1 = cdlt.create_operand_template("op1", OP_DTYPES, [N, C, H, W], default_dtype=OP_DTYPES[2])
        op2 = cdlt.create_operand_template("op3", OP_DTYPES, [N, C, H, W], default_dtype=OP_DTYPES[2])
        out = cdlt.create_operand_template("out", OP_DTYPES, [N, C, H, W], default_dtype=OP_DTYPES[2])
        cdlt.set_inputs([op1, op2])
        cdlt.set_outputs([out])

        simd_size = cdlt.dummy_op("SIMD_SIZE", cdlt.hag.all_subgraph_nodes['SIMD'].dimensions[0])

        alpha = cdlt.create_temp_operand([simd_size], "IMM")

        cdlt.configure('start', 'SIMD')
        alphaval = cdlt.dummy_op("alpha", cdlt.node.alpha, dtype="FXP32")
        cdlt.configure("start", "IMM", immediate_value=alphaval, index=0)
        m0 = create_immediate_with_operand(cdlt, QUANT_SCALE, simd_size=simd_size)
        nshift = create_immediate_with_operand(cdlt, SIGN_SHIFT, simd_size=simd_size)

        with cdlt.loop(C) as c:
            with cdlt.loop(N) as n:
                with cdlt.loop(H) as h:
                    with cdlt.loop(W) as w:
                        cdlt.transfer(op1, ["DRAM", "VMEM2"])
                        cdlt.transfer(op2, ["DRAM", "VMEM1"])
                        indices = (n,c,h,w)
                        out.set_write_destination('VMEM1')
                        op1.set_write_destination("VMEM2")
                        op2.set_write_destination("VMEM1")

                        cdlt.compute("ADD", [op1[indices], op2[indices]], [op1[indices]],
                                     target="SIMD")
                        cdlt.compute("LEAKY_RELU", [op1[indices], alpha], [out[indices]],
                                     target="SIMD")
                        cdlt.transfer(out, ["VMEM1", "DRAM"])
            cdlt.configure('end', 'SIMD')
    cdlt = add_simd_constraint(hag, cdlt, "C")
    return cdlt

def leaky_relu_add(hag):
    with CodeletTemplate('leaky_relu_add') as cdlt:
        N = cdlt.dummy_op("N", cdlt.node.inputs[0].shape[0])
        C = cdlt.dummy_op("C", cdlt.node.inputs[0].shape[1])
        H = cdlt.dummy_op("H", cdlt.node.inputs[0].shape[2])
        W = cdlt.dummy_op("W", cdlt.node.inputs[0].shape[3])
        op1 = cdlt.create_operand_template("op1", OP_DTYPES, [N, C, H, W], default_dtype=OP_DTYPES[2])
        op2 = cdlt.create_operand_template("op3", OP_DTYPES, [N, C, H, W], default_dtype=OP_DTYPES[2])
        out = cdlt.create_operand_template("out", OP_DTYPES, [N, C, H, W], default_dtype=OP_DTYPES[2])
        cdlt.set_inputs([op1, op2])
        cdlt.set_outputs([out])

        simd_size = cdlt.dummy_op("SIMD_SIZE", cdlt.hag.all_subgraph_nodes['SIMD'].dimensions[0])

        alpha = cdlt.create_temp_operand([simd_size], "IMM")

        cdlt.configure('start', 'SIMD')
        alphaval = cdlt.dummy_op("alpha", cdlt.node.alpha, dtype="FXP32")
        cdlt.configure("start", "IMM", immediate_value=alphaval, index=0)
        m0 = create_immediate_with_operand(cdlt, QUANT_SCALE, simd_size=simd_size)
        nshift = create_immediate_with_operand(cdlt, SIGN_SHIFT, simd_size=simd_size)

        with cdlt.loop(C) as c:
            with cdlt.loop(N) as n:
                with cdlt.loop(H) as h:
                    with cdlt.loop(W) as w:
                        cdlt.transfer(op1, ["DRAM", "VMEM2"])
                        cdlt.transfer(op2, ["DRAM", "VMEM1"])
                        indices = (n,c,h,w)
                        out.set_write_destination('VMEM1')
                        op1.set_write_destination("VMEM2")
                        op2.set_write_destination("VMEM1")

                        cdlt.compute("LEAKY_RELU", [op1[indices], alpha], [op1[indices]],
                                     target="SIMD")
                        cdlt.compute("ADD", [op1[indices], op2[indices]], [out[indices]],
                                     target="SIMD")
                        cdlt.transfer(out, ["VMEM1", "DRAM"])
        cdlt.configure('end', 'SIMD')
    cdlt = add_simd_constraint(hag, cdlt, "C")
    return cdlt

def clip_depthwise_conv_bias(hag: ArchitectureNode):
    # TODO: De-duplicate replicated outer loops for a given VMEM
    # TODO: Add zero constant
    # TODO: Replicate inner loops on a per-operand basis, and use the same offset from the previous tile
    # TODO: Make sure the output operands use 0 for it's offset
    # TODO: Need to figure out how to change the memory layout
    with CodeletTemplate("clip_depthwise_conv_bias") as cdlt:
        N = cdlt.dummy_op("N", cdlt.node.inputs[0].shape[0])
        C = cdlt.dummy_op("C", cdlt.node.inputs[0].shape[1])
        ONE = cdlt.dummy_op("ONE", cdlt.node.inputs[1].shape[1])
        KH = cdlt.dummy_op("KH", cdlt.node.inputs[1].shape[2])
        KW = cdlt.dummy_op("KW", cdlt.node.inputs[1].shape[3])
        OH = cdlt.dummy_op("OH", cdlt.node.outputs[0].shape[2])
        OW = cdlt.dummy_op("OW", cdlt.node.outputs[0].shape[3])
        IH = cdlt.dummy_op("IH", cdlt.node.inputs[0].shape[2])
        IW = cdlt.dummy_op("IW", cdlt.node.inputs[0].shape[3])

        data = cdlt.create_operand_template("data", OP_DTYPES, [N, C, IH, IW], default_dtype=OP_DTYPES[2])
        weight = cdlt.create_operand_template("weight", OP_DTYPES, [C, ONE, KH, KW], default_dtype=OP_DTYPES[2])
        bias = cdlt.create_operand_template("bias", OP_DTYPES, [C], default_dtype=OP_DTYPES[2])
        out = cdlt.create_operand_template("out", OP_DTYPES, [N, C, OH, OW], default_dtype=OP_DTYPES[2])
        cdlt.set_inputs([data, weight, bias])
        cdlt.set_outputs([out])
        # Setup min/max params
        minval = cdlt.dummy_op("min", cdlt.node.kwargs['minval'], dtype="FXP32")
        maxval = cdlt.dummy_op("max", cdlt.node.kwargs['maxval'], dtype="FXP32")
        SIMD_SIZE = cdlt.dummy_op("SIMD_SIZE", cdlt.hag.all_subgraph_nodes['SIMD'].dimensions[0])
        min_op = cdlt.create_temp_operand([SIMD_SIZE], "IMM")
        max_op = cdlt.create_temp_operand([SIMD_SIZE], "IMM")

        stride = cdlt.dummy_op("stride", cdlt.node.stride)
        pad = cdlt.dummy_op("pad", cdlt.node.pad_int)
        # OS ->
        cdlt.configure("start", "SIMD")
        cdlt.configure("start", "IMM", immediate_value=0, index=0)
        m0 = create_immediate_with_operand(cdlt, QUANT_SCALE, simd_size=SIMD_SIZE)
        nshift = create_immediate_with_operand(cdlt, SIGN_SHIFT, simd_size=SIMD_SIZE)
        zero = create_immediate_with_operand(cdlt, 0, simd_size=SIMD_SIZE)
        cdlt.configure("start", "IMM", immediate_value=minval, index=len(cdlt.temps) + 1)
        cdlt.configure("start", "IMM", immediate_value=maxval, index=len(cdlt.temps) + 2)
        with cdlt.loop(ONE) as one:
            with cdlt.loop(N) as n:
                with cdlt.loop(C) as c:
                    with cdlt.loop(OH) as y:
                        with cdlt.loop(OW) as x:
                            with cdlt.loop(KH) as kh:
                                with cdlt.loop(KW) as kw:
                                    cdlt.transfer(weight, ["DRAM", "VMEM1"])
                                    cdlt.transfer(data, ["DRAM", "VMEM2"])
                                    cdlt.transfer(bias, ["DRAM", "VMEM1"])
                                    cdlt.transfer(out, ["DRAM", "VMEM2"])
                                    out.set_write_destination("VMEM2")
                                    data.set_write_destination("VMEM2")
                                    indices = (n, c, y * stride + kh, x * stride + kw)
                                    cdlt.compute("MAX", [data[indices], max_op],
                                                 [data[indices]
                                                  ],
                                                 target="SIMD")

                                    cdlt.compute("MIN", [data[indices], min_op],
                                                 [data[indices]],
                                                 target="SIMD")

                                    cdlt.compute("MACC", [data[indices], weight[c, one, kh, kw], out[n, c, y, x]], [out[n, c, y, x]], target="SIMD")
                                    cdlt.compute("ADD", [out[n, c, y, x], bias[c]], [out[n, c, y, x]], target="SIMD")
                                    indices = (n, c, y, x)
                                    cdlt.transfer(out, ["VMEM2", "DRAM"])
        cdlt.configure("end", "SIMD")

    cdlt = add_simd_constraint(hag, cdlt, "C")
    cdlt = add_simd_tile_constraint(hag, cdlt, ["KH", "KW"])


    return cdlt

def clip_depthwise_conv_bias_clip(hag: ArchitectureNode):
    # TODO: De-duplicate replicated outer loops for a given VMEM
    # TODO: Add zero constant
    # TODO: Replicate inner loops on a per-operand basis, and use the same offset from the previous tile
    # TODO: Make sure the output operands use 0 for it's offset
    # TODO: Need to figure out how to change the memory layout
    with CodeletTemplate("clip_depthwise_conv_bias_clip") as cdlt:
        N = cdlt.dummy_op("N", cdlt.node.inputs[0].shape[0])
        C = cdlt.dummy_op("C", cdlt.node.inputs[0].shape[1])
        ONE = cdlt.dummy_op("ONE", cdlt.node.inputs[1].shape[1])
        KH = cdlt.dummy_op("KH", cdlt.node.inputs[1].shape[2])
        KW = cdlt.dummy_op("KW", cdlt.node.inputs[1].shape[3])
        OH = cdlt.dummy_op("OH", cdlt.node.outputs[0].shape[2])
        OW = cdlt.dummy_op("OW", cdlt.node.outputs[0].shape[3])
        IH = cdlt.dummy_op("IH", cdlt.node.inputs[0].shape[2])
        IW = cdlt.dummy_op("IW", cdlt.node.inputs[0].shape[3])

        data = cdlt.create_operand_template("data", OP_DTYPES, [N, C, IH, IW], default_dtype=OP_DTYPES[2])
        weight = cdlt.create_operand_template("weight", OP_DTYPES, [C, ONE, KH, KW], default_dtype=OP_DTYPES[2])
        bias = cdlt.create_operand_template("bias", OP_DTYPES, [C], default_dtype=OP_DTYPES[2])
        out = cdlt.create_operand_template("out", OP_DTYPES, [N, C, OH, OW], default_dtype=OP_DTYPES[2])
        cdlt.set_inputs([data, weight, bias])
        cdlt.set_outputs([out])
        # Setup min/max params
        minval = cdlt.dummy_op("min", cdlt.node.kwargs['minval'], dtype="FXP32")
        maxval = cdlt.dummy_op("max", cdlt.node.kwargs['maxval'], dtype="FXP32")
        SIMD_SIZE = cdlt.dummy_op("SIMD_SIZE", cdlt.hag.all_subgraph_nodes['SIMD'].dimensions[0])
        min_op = cdlt.create_temp_operand([SIMD_SIZE], "IMM")
        max_op = cdlt.create_temp_operand([SIMD_SIZE], "IMM")

        stride = cdlt.dummy_op("stride", cdlt.node.stride)
        pad = cdlt.dummy_op("pad", cdlt.node.pad_int)
        # OS ->
        cdlt.configure("start", "SIMD")
        cdlt.configure("start", "IMM", immediate_value=0, index=0)
        m0 = create_immediate_with_operand(cdlt, QUANT_SCALE, simd_size=SIMD_SIZE)
        nshift = create_immediate_with_operand(cdlt, SIGN_SHIFT, simd_size=SIMD_SIZE)
        zero = create_immediate_with_operand(cdlt, 0, simd_size=SIMD_SIZE)
        cdlt.configure("start", "IMM", immediate_value=minval, index=len(cdlt.temps) + 1)
        cdlt.configure("start", "IMM", immediate_value=maxval, index=len(cdlt.temps) + 2)
        with cdlt.loop(ONE) as one:
            with cdlt.loop(N) as n:
                with cdlt.loop(C) as c:
                    with cdlt.loop(OH) as y:
                        with cdlt.loop(OW) as x:
                            with cdlt.loop(KH) as kh:
                                with cdlt.loop(KW) as kw:
                                    cdlt.transfer(weight, ["DRAM", "VMEM1"])
                                    cdlt.transfer(data, ["DRAM", "VMEM2"])
                                    cdlt.transfer(bias, ["DRAM", "VMEM1"])
                                    cdlt.transfer(out, ["DRAM", "VMEM2"])
                                    out.set_write_destination("VMEM2")
                                    data.set_write_destination("VMEM2")
                                    indices = (n, c, y * stride + kh, x * stride + kw)
                                    cdlt.compute("MAX", [data[indices], max_op],
                                                 [data[indices]
                                                  ],
                                                 target="SIMD")

                                    cdlt.compute("MIN", [data[indices], min_op],
                                                 [data[indices]],
                                                 target="SIMD")

                                    cdlt.compute("MACC", [data[indices], weight[c, one, kh, kw], out[n, c, y, x]], [out[n, c, y, x]], target="SIMD")
                                    cdlt.compute("ADD", [out[n, c, y, x], bias[c]], [out[n, c, y, x]], target="SIMD")
                                    indices = (n, c, y, x)
                                    cdlt.compute("MAX", [out[indices], max_op],
                                                 [out[indices]
                                                  ],
                                                 target="SIMD")

                                    cdlt.compute("MIN", [out[indices], min_op],
                                                 [out[indices]],
                                                 target="SIMD")
                                    cdlt.transfer(out, ["VMEM2", "DRAM"])
        cdlt.configure("end", "SIMD")

    cdlt = add_simd_constraint(hag, cdlt, "C")
    cdlt = add_simd_tile_constraint(hag, cdlt, ["KH", "KW"])


    return cdlt

if SW_PIPELINE_TEST:
    UNQUANT_FUSION_OP_INFO = {
        'div_add': {
            'cdlt': div_add,
            'seq': ["Div", "Add"]
        },
        'add_relu': {
            'cdlt': add_relu,
            'seq': ['Add', 'Relu'],
        },
        'add_leaky_relu': {
            'cdlt': add_leaky_relu,
            'seq': ['Add', 'LeakyRelu'],
        },
        'leaky_relu_add': {
            'cdlt': leaky_relu_add,
            'seq': ['LeakyRelu', 'Add'],
        },
        'clip_depthwise_conv_bias': {
            'cdlt': clip_depthwise_conv_bias,
            'seq': ['Clip', 'DepthwiseConv'],

        },
        'clip_depthwise_conv_bias_clip': {
            'cdlt': clip_depthwise_conv_bias_clip,
            'seq': ['Clip', 'DepthwiseConv', 'Clip'],

        },
        'add_add': {
          'cdlt': add_add,
          'seq': ["Add", "Add"]
        },
        'add_add4d': {
            'cdlt': add_add4d,
            'seq': ["Add", "Add"]
        },
        'mul_add': {
            'cdlt': mul_add,
            'seq': ["Mul", "Add"]
        },
        'sub_mul': {
            'cdlt': sub_mul,
            'seq': ["Sub", "Mul"]
        },
        'sub_pow': {
            'cdlt': sub_pow,
            'seq': ["Sub", "Pow"],
        },
        'add_sqrt_div': {
            'cdlt': add_sqrt_div,
            'seq': ["Add", "Sqrt", "Div"],
        },
        'matmul_add': {
            'cdlt': matmul_add,
            'seq': ["MatMul", "Add"]
        },

        'single_layer_info':
            {
                'Conv' : {'inputs': 3, 'outputs': 1},
                'Relu' : {'inputs': 1, 'outputs': 1},
                'LeakyRelu' : {'inputs': 1, 'outputs': 1},
                'Add' : {'inputs': 2, 'outputs': 1},
                'MaxPool': {'inputs': 1, 'outputs': 1}
            }
    }
else:
    UNQUANT_FUSION_OP_INFO = {
    'add_add': {
      'cdlt': add_add,
      'seq': ["Add", "Add"]
    },
    'mul_add': {
        'cdlt': mul_add,
        'seq': ["Mul", "Add"]
    },
    'sub_mul': {
        'cdlt': sub_mul,
        'seq': ["Sub", "Mul"]
    },

    'sub_pow': {
        'cdlt': sub_pow,
        'seq': ["Sub", "Pow"],
    },
    'add_sqrt_div': {
        'cdlt': add_sqrt_div,
        'seq': ["Add", "Sqrt", "Div"],
    },
    'matmul_add': {
        'cdlt': matmul_add,
        'seq': ["MatMul", "Add"]
    },
    'matmul_add_add': {
        'cdlt': matmul_add_add,
        'seq': ["MatMul", "Add", "Add"]
    },
    'matmul_add_gelu': {
        'cdlt': matmul_add_gelu,
        'seq': ["MatMul", "Add", "Gelu"]
    },
    'matmul_div_add': {
        'cdlt': matmul_div_add,
        'seq': ["MatMul", "Div", "Add"]
    },
    'conv_bias_relu': {
        'cdlt': conv_relu,
        'seq': ['Conv', 'Relu']
    },
    'conv_bias_add_relu': {
        'cdlt': conv_add_relu,
        'seq': ['Conv', 'Add', 'Relu'],
    },
    'conv_bias_add': {
        'cdlt': conv_add,
        'seq': ['Conv', 'Add'],
    },
    'conv_bias_clip': {
        'cdlt': conv_clip,
        'seq': ['Conv', 'Clip'],
    },
    'depthwise_conv_bias_clip': {
        'cdlt': depthwise_conv_clip,
        'seq': ['DepthwiseConv', 'Clip'],
    },
    'conv_bias_leaky_relu': {
        'cdlt': conv_leaky_relu,
        'seq': ['Conv', 'LeakyRelu']
    },
    'conv_bias_add_leaky_relu': {
        'cdlt': conv_add_leaky_relu,
        'seq': ['Conv', 'Add', 'LeakyRelu'],
    },
    'conv_bias_leaky_relu_add': {
        'cdlt': conv_leaky_relu_add,
        'seq': ['Conv', 'LeakyRelu', 'Add'],
    },
    'conv_bias_clip_depthwise_conv_bias': {
        'cdlt': conv_bias_clip_depthwise_conv_bias,
        'seq': ['Conv', 'Clip', 'DepthwiseConv'],

    },
    'conv_bias_clip_depthwise_conv_bias_clip': {
        'cdlt': conv_bias_clip_depthwise_conv_bias_clip,
        'seq': ['Conv', 'Clip', 'DepthwiseConv', 'Clip'],

    },
    'single_layer_info':
        {
            'Conv' : {'inputs': 3, 'outputs': 1},
            'Relu' : {'inputs': 1, 'outputs': 1},
            'LeakyRelu' : {'inputs': 1, 'outputs': 1},
            'Add' : {'inputs': 2, 'outputs': 1},
            'MaxPool': {'inputs': 1, 'outputs': 1}
        }
}

UNQUANT_FUSION_CODELETS = {k : v['cdlt'] for k,v in UNQUANT_FUSION_OP_INFO.items() if k != 'single_layer_info'}
