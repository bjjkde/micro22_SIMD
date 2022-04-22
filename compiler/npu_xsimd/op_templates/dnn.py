from op_templates.adl.graph import ArchitectureNode
from op_templates.templates.op_template import CodeletTemplate
from examples.genesys import OP_DTYPES, FXP_CONFIGS, QUANT_SCALE, SIGN_SHIFT
import numpy as np
from . import range_from_cfg, add_simd_constraint, create_immediate_with_operand, add_simd_tile_constraint, add_scale_and_cast_op




def depthwise_conv(hag: ArchitectureNode):
    # TODO: De-duplicate replicated outer loops for a given VMEM
    # TODO: Add zero constant
    # TODO: Replicate inner loops on a per-operand basis, and use the same offset from the previous tile
    # TODO: Make sure the output operands use 0 for it's offset
    # TODO: Need to figure out how to change the memory layout
    with CodeletTemplate("depthwise_conv") as cdlt:
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
        out = cdlt.create_operand_template("out", OP_DTYPES, [N, C, OH, OW], default_dtype=OP_DTYPES[2])
        cdlt.set_inputs([data, weight])
        cdlt.set_outputs([out])

        stride = cdlt.dummy_op("stride", cdlt.node.stride)
        pad = cdlt.dummy_op("pad", cdlt.node.pad_int)
        # OS ->
        cdlt.configure("start", "SIMD")
        cdlt.configure("start", "IMM", immediate_value=0, index=0)

        with cdlt.loop(ONE) as one:
            with cdlt.loop(N) as n:
                with cdlt.loop(C) as c:
                    with cdlt.loop(OH) as y:
                        with cdlt.loop(OW) as x:
                            with cdlt.loop(KH) as kh:
                                with cdlt.loop(KW) as kw:
                                    cdlt.transfer(weight, ["DRAM", "VMEM1"])
                                    cdlt.transfer(data, ["DRAM", "VMEM2"])
                                    cdlt.transfer(out, ["DRAM", "VMEM2"])
                                    out.set_write_destination("VMEM2")
                                    cdlt.compute("MACC", [data[n, c, y * stride + kh, x * stride + kw], weight[c, one, kh, kw], out[n, c, y, x]], [out[n, c, y, x]], target="SIMD")
                                    cdlt.transfer(out, ["VMEM2", "DRAM"])
        cdlt.configure("end", "SIMD")

    cdlt = add_simd_constraint(hag, cdlt, "C")

    return cdlt


def depthwise_conv_bias(hag: ArchitectureNode):
    # TODO: De-duplicate replicated outer loops for a given VMEM
    # TODO: Add zero constant
    # TODO: Replicate inner loops on a per-operand basis, and use the same offset from the previous tile
    # TODO: Make sure the output operands use 0 for it's offset
    # TODO: Need to figure out how to change the memory layout
    with CodeletTemplate("depthwise_conv_bias") as cdlt:
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

        stride = cdlt.dummy_op("stride", cdlt.node.stride)
        pad = cdlt.dummy_op("pad", cdlt.node.pad_int)
        # OS ->
        cdlt.configure("start", "SIMD")
        cdlt.configure("start", "IMM", immediate_value=0, index=0)

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
                                    cdlt.compute("MACC", [data[n, c, y * stride + kh, x * stride + kw], weight[c, one, kh, kw], out[n, c, y, x]], [out[n, c, y, x]], target="SIMD")
                                    cdlt.compute("ADD", [out[n, c, y, x], bias[c]], [out[n, c, y, x]], target="SIMD")
                                    cdlt.transfer(out, ["VMEM2", "DRAM"])
        cdlt.configure("end", "SIMD")

    cdlt = add_simd_constraint(hag, cdlt, "C")

    return cdlt


def batch_norm(hag: ArchitectureNode):

    with CodeletTemplate("batch_norm") as cdlt:

        N = cdlt.dummy_op("N", cdlt.node.inputs[0].shape[0])
        C = cdlt.dummy_op("C", cdlt.node.inputs[0].shape[1])
        H = cdlt.dummy_op("H", cdlt.node.inputs[0].shape[2])
        W = cdlt.dummy_op("W", cdlt.node.inputs[0].shape[3])

        #
        data = cdlt.create_operand_template("data", OP_DTYPES, [N, C, H, W], default_dtype=OP_DTYPES[2])
        scale = cdlt.create_operand_template("scale", OP_DTYPES, [C], default_dtype=OP_DTYPES[2])
        offset = cdlt.create_operand_template("offset", OP_DTYPES, [C], default_dtype=OP_DTYPES[2])
        mean = cdlt.create_operand_template("mean", OP_DTYPES, [C], default_dtype=OP_DTYPES[2])
        istd = cdlt.create_operand_template("istd", OP_DTYPES, [C], default_dtype=OP_DTYPES[2])

        out = cdlt.create_operand_template("out", OP_DTYPES, [N, C, H, W], default_dtype=OP_DTYPES[2])
        cdlt.set_inputs([data, scale, offset, mean, istd])
        cdlt.set_outputs([out])

        numer = cdlt.create_operand_template("numer", OP_DTYPES, [N, C, H, W], default_dtype=OP_DTYPES[2])
        denom = cdlt.create_operand_template("denom", OP_DTYPES, [N, C, H, W], default_dtype=OP_DTYPES[2])
        cdlt.add_temp_operand(numer)
        cdlt.add_temp_operand(denom)

        cdlt.configure("start", "SIMD")
        with cdlt.loop(C) as c:
            with cdlt.loop(N) as n:
                with cdlt.loop(H) as h:
                    with cdlt.loop(W) as w:
                        cdlt.transfer(data, ["DRAM", "VMEM1"])
                        cdlt.transfer(out, ["DRAM", "VMEM1"])
                        cdlt.transfer(mean, ["DRAM", "VMEM2"])
                        cdlt.transfer(istd, ["DRAM", "VMEM2"])
                        cdlt.transfer(scale, ["DRAM", "VMEM2"])
                        cdlt.transfer(offset, ["DRAM", "VMEM2"])
                        numer.set_write_destination("VMEM1")
                        denom.set_write_destination("VMEM2")
                        out.set_write_destination("VMEM1")
                        cdlt.compute("SUB", [data[n, c, h, w], mean[c]], [numer[n, c, h, w]], target="SIMD")
                        cdlt.compute("MUL", [numer[n, c, h, w], istd[c]], [out[n, c, h, w]], target="SIMD")
                        cdlt.compute("MUL", [out[n, c, h, w], scale[c]], [out[n, c, h, w]], target="SIMD")
                        cdlt.compute("ADD", [out[n, c, h, w], offset[c]], [out[n, c, h, w]], target="SIMD")
                        cdlt.transfer(out, ["VMEM1", "DRAM"])
        cdlt.configure("end", "SIMD")

    cdlt = add_simd_constraint(hag, cdlt, "C")

    return cdlt


def mean_var(hag: ArchitectureNode):
    with CodeletTemplate("mean_var") as cdlt:
        N = cdlt.dummy_op("N", cdlt.node.inputs[0].shape[0])
        C = cdlt.dummy_op("C", cdlt.node.inputs[0].shape[1])
        H = cdlt.dummy_op("H", cdlt.node.inputs[0].shape[2])
        W = cdlt.dummy_op("W", cdlt.node.inputs[0].shape[3])

        data = cdlt.create_operand_template("data", OP_DTYPES, [N, C, H, W], default_dtype=OP_DTYPES[2])
        mean = cdlt.create_operand_template("mean", OP_DTYPES, [C], default_dtype=OP_DTYPES[2])
        istd = cdlt.create_operand_template("istd", OP_DTYPES, [C], default_dtype=OP_DTYPES[2])
        temp1 = cdlt.create_operand_template("temp1", OP_DTYPES, [C], default_dtype=OP_DTYPES[2])
        temp2 = cdlt.create_operand_template("temp2", OP_DTYPES, [C], default_dtype=OP_DTYPES[2])
        temp3 = cdlt.create_operand_template("temp3", OP_DTYPES, [C], default_dtype=OP_DTYPES[2])
        cdlt.add_temp_operand(temp1)
        cdlt.add_temp_operand(temp2)
        cdlt.add_temp_operand(temp3)
        temp1.start_location = "VMEM1"
        temp2.start_location = "VMEM2"
        temp3.start_location = "VMEM2"
        temp1.set_write_destination("VMEM1")
        temp2.set_write_destination("VMEM1")
        temp3.set_write_destination("VMEM1")

        cdlt.set_inputs([data])
        cdlt.set_outputs([mean, istd])
        denom = cdlt.dummy_op("denom", cdlt.node.inputs[0].shape[0]*cdlt.node.inputs[0].shape[2]*cdlt.node.inputs[0].shape[3])
        SIMD_SIZE = cdlt.dummy_op("SIMD_SIZE", cdlt.hag.all_subgraph_nodes['SIMD'].dimensions[0])
        denom_op = cdlt.create_temp_operand([SIMD_SIZE], "IMM")
        eps_op = cdlt.create_temp_operand([SIMD_SIZE], "IMM")
        cdlt.configure("start", "IMM", immediate_value=denom, index=0)
        cdlt.configure("start", "IMM", immediate_value=0.0001, index=1)


        with cdlt.loop(C) as c:
            with cdlt.loop(N) as n:
                with cdlt.loop(H) as h:
                    with cdlt.loop(W) as w:
                        cdlt.transfer(data, ["DRAM", "VMEM1"])
                        cdlt.transfer(mean, ["DRAM", "VMEM1"])
                        cdlt.transfer(istd, ["DRAM", "VMEM2"])
                        data.set_write_destination("VMEM1")
                        mean.set_write_destination("VMEM1")
                        istd.set_write_destination("VMEM2")
                        cdlt.compute("ADD", [data[n, c, h, w], mean[c]], [mean[c]], target="SIMD")
                        cdlt.compute("MUL", [data[n, c, h, w], data[n, c, h, w]], [temp1[c]], target="SIMD")
                        cdlt.compute("ADD", [istd[c], temp1[c]], [istd[c]], target="SIMD")
            cdlt.compute("MUL", [mean[c], mean[c]], [temp2[c]], target="SIMD")
            cdlt.compute("DIV", [temp2[c], denom_op], [temp3[c]], target="SIMD")
            cdlt.compute("SUB", [istd[c], temp3[c]], [istd[c]], target="SIMD")
            cdlt.compute("DIV", [istd[c], denom_op], [istd[c]], target="SIMD")
            cdlt.compute("ADD", [istd[c], eps_op], [istd[c]], target="SIMD")
            cdlt.compute("INV_SQRT", [istd[c]], [istd[c]], target="SIMD")
            cdlt.compute("DIV", [mean[c], denom_op], [mean[c]], target="SIMD")
            cdlt.transfer(mean, ["VMEM1", "DRAM"])
            cdlt.transfer(istd, ["VMEM2", "DRAM"])
        cdlt.configure("end", "SIMD")
    cdlt = add_simd_constraint(hag, cdlt, "C")

    return cdlt


def cross_entropy_loss(hag: ArchitectureNode):

    with CodeletTemplate("cross_entropy_loss") as cdlt:
        N = cdlt.dummy_op("N", cdlt.node.inputs[0].shape[0])
        C = cdlt.dummy_op("C", cdlt.node.inputs[0].shape[1])
        res = cdlt.create_operand_template("res", OP_DTYPES, [N, C], default_dtype=OP_DTYPES[2])
        target = cdlt.create_operand_template("target", OP_DTYPES, [N], default_dtype=OP_DTYPES[2])
        loss = cdlt.create_operand_template("loss", OP_DTYPES, [N, C], default_dtype=OP_DTYPES[2])
        cdlt.set_inputs([res, target])
        cdlt.set_outputs([loss])
        temp1 = cdlt.create_operand_template("temp1", OP_DTYPES, [N, C], default_dtype=OP_DTYPES[2])
        temp1.start_location = "VMEM1"
        temp1.set_write_destination("VMEM1")
        cdlt.add_temp_operand(temp1)
        cdlt.configure("start", "SIMD")

        with cdlt.loop(N) as n:
            with cdlt.loop(C) as c:
                cdlt.transfer(res, ["DRAM", "VMEM1"])
                cdlt.transfer(loss, ["DRAM", "VMEM1"])
                loss.set_write_destination("VMEM1")
                cdlt.compute("EXP", [res[n, c]], [temp1[n, c]], target="SIMD")
                cdlt.compute("ADD", [temp1[n, c], loss[n, c]], [loss[n, c]], target="SIMD")
            cdlt.compute("DIV", [temp1[n, c], loss[n, c]], [loss[n, c]], target="SIMD")
            cdlt.transfer(loss, ["VMEM1", "DRAM"])
        cdlt.configure("end", "SIMD")

    cdlt = add_simd_constraint(hag, cdlt, "C")
    return cdlt


def maxpool2d(hag: ArchitectureNode):
    #

    # # TODO: Add option to create operand
    with CodeletTemplate("max_pool") as cdlt:
        N = cdlt.dummy_op("N", cdlt.node.inputs[0].shape[0])
        C = cdlt.dummy_op("C", cdlt.node.inputs[0].shape[1])
        KH = cdlt.dummy_op("KH", cdlt.node.kernel_size[0])
        KW = cdlt.dummy_op("KW", cdlt.node.kernel_size[1])
        OH = cdlt.dummy_op("OH", cdlt.node.outputs[0].shape[2])
        OW = cdlt.dummy_op("OW", cdlt.node.outputs[0].shape[3])
        IW = cdlt.dummy_op("IW", cdlt.node.inputs[0].shape[3])
        IH = cdlt.dummy_op("IH", cdlt.node.inputs[0].shape[2])

        data = cdlt.create_operand_template("data", OP_DTYPES, [N, C, IH, IW], default_dtype=OP_DTYPES[2])
        out = cdlt.create_operand_template("out", OP_DTYPES, [N, C, OH, OW], default_dtype=OP_DTYPES[2])

        cdlt.set_inputs([data])
        cdlt.set_outputs([out])
        min_val, _ = range_from_cfg(FXP_CONFIGS[str(OP_DTYPES[2])])

        cdlt.configure("start", "SIMD")
        cdlt.configure("start", "IMM", immediate_value=min_val, index=0)
        pad = cdlt.dummy_op("pad", cdlt.node.pad[0])
        sy = cdlt.dummy_op("sy", cdlt.node.stride[0])
        sx = cdlt.dummy_op("sx", cdlt.node.stride[1])
        with cdlt.loop(N) as n:
            with cdlt.loop(C) as c:
                with cdlt.loop(KH) as kh:
                    with cdlt.loop(KW) as kw:
                        with cdlt.loop(OH) as y:
                            with cdlt.loop(OW) as x:
                                cdlt.transfer(data, ["DRAM", "VMEM1"])
                                # TODO: Initialize output as negative infinity at compile time
                                cdlt.transfer(out, ["DRAM", "VMEM2"])
                                out.set_write_destination("VMEM2")
                                cdlt.compute("MAX", [data[n, c, y*sy + kh, x*sx + kw], out[n, c, y, x]], [out[n, c, y, x]], target="SIMD")
                                cdlt.transfer(out, ["VMEM2", "DRAM"])
        cdlt.configure("end", "SIMD")
    cdlt = add_simd_constraint(hag, cdlt, "C")
    return cdlt


def averagepool2d(hag: ArchitectureNode):

    with CodeletTemplate("avg_pool") as cdlt:
        N = cdlt.dummy_op("N", cdlt.node.inputs[0].shape[0])
        C = cdlt.dummy_op("C", cdlt.node.inputs[0].shape[1])
        KH = cdlt.dummy_op("KH", cdlt.node.kernel_size[0])
        KW = cdlt.dummy_op("KW", cdlt.node.kernel_size[1])
        OH = cdlt.dummy_op("OH", cdlt.node.outputs[0].shape[2])
        OW = cdlt.dummy_op("OW", cdlt.node.outputs[0].shape[3])
        IH = cdlt.dummy_op("IH", cdlt.node.inputs[0].shape[2])
        IW = cdlt.dummy_op("IW", cdlt.node.inputs[0].shape[3])
        denom = cdlt.dummy_op("denom", cdlt.node.inputs[0].shape[2]*cdlt.node.inputs[0].shape[3])
        SIMD_SIZE = cdlt.dummy_op("SIMD_SIZE", cdlt.hag.all_subgraph_nodes['SIMD'].dimensions[0])
        data = cdlt.create_operand_template("data", OP_DTYPES, [N, C, IH, IW], default_dtype=OP_DTYPES[2])
        out = cdlt.create_operand_template("out", OP_DTYPES, [N, C, OH, OW], default_dtype=OP_DTYPES[2])
        cdlt.set_inputs([data])
        cdlt.set_outputs([out])
        denom_op = cdlt.create_temp_operand([SIMD_SIZE], "IMM")

        cdlt.configure("start", "SIMD")
        # denom = IH*IW
        cdlt.configure("start", "IMM", immediate_value=denom, index=0)
        cdlt.configure("start", "IMM", immediate_value=0, index=1)
        sy = cdlt.dummy_op("sy", cdlt.node.stride[0])
        sx = cdlt.dummy_op("sx", cdlt.node.stride[1])
        with cdlt.loop(N) as n:
            with cdlt.loop(C) as c:
                with cdlt.loop(KH) as kh:
                    with cdlt.loop(KW) as kw:
                        with cdlt.loop(OH) as y:
                            with cdlt.loop(OW) as x:
                                cdlt.transfer(data, ["DRAM", "VMEM1"])
                                # TODO: Initialize output as negative infinity at compile time
                                cdlt.transfer(out, ["DRAM", "VMEM2"])
                                out.set_write_destination("VMEM2")
                                cdlt.compute("ADD", [data[n, c, y*sy + kh, x*sx + kw], out[n, c, y, x]], [out[n, c, y, x]], target="SIMD")
                                cdlt.compute("MUL", [out[n, c, y, x], denom_op], [out[n, c, y, x]], target="SIMD")
                                cdlt.transfer(out, ["VMEM2", "DRAM"])
        cdlt.configure("end", "SIMD")
    cdlt = add_simd_constraint(hag, cdlt, "C")

    return cdlt


def global_avg_pool(hag: ArchitectureNode):
    #

    # # TODO: Add option to create operand
    with CodeletTemplate("global_avg_pool") as cdlt:
        N = cdlt.dummy_op("N", cdlt.node.inputs[0].shape[0])
        C = cdlt.dummy_op("C", cdlt.node.inputs[0].shape[1])
        IH = cdlt.dummy_op("IH", cdlt.node.inputs[0].shape[2])
        IW = cdlt.dummy_op("IW", cdlt.node.inputs[0].shape[3])
        OH = cdlt.dummy_op("OH", cdlt.node.outputs[0].shape[2])
        OW = cdlt.dummy_op("OW", cdlt.node.outputs[0].shape[3])

        data = cdlt.create_operand_template("data", OP_DTYPES, [N, C, IH, IW], default_dtype=OP_DTYPES[2])
        out = cdlt.create_operand_template("out", OP_DTYPES, [N, C, OH, OW], default_dtype=OP_DTYPES[2])

        cdlt.set_inputs([data])
        cdlt.set_outputs([out])
        # Change this to be the reciprocal as a FXP value

        denom = cdlt.dummy_op("denom", 1/(cdlt.node.inputs[0].shape[2]*cdlt.node.inputs[0].shape[3]), dtype="FXP32")
        SIMD_SIZE = cdlt.dummy_op("SIMD_SIZE", cdlt.hag.all_subgraph_nodes['SIMD'].dimensions[0])

        cdlt.configure("start", "SIMD")
        ## IMPORTANT: The configure index needs to correspond to the order in which the corresponding temporary is created
        # This is a temporary hotfix to enable IMM value indexing during instruction generation
        cdlt.configure("start", "IMM", immediate_value=0, index=0)
        zero_op = cdlt.create_temp_operand([SIMD_SIZE], "IMM")

        cdlt.configure("start", "IMM", immediate_value=denom, index=1)
        denom_op = cdlt.create_temp_operand([SIMD_SIZE], "IMM")

        with cdlt.loop(OH) as oy:
            with cdlt.loop(OW) as ox:
                with cdlt.loop(IH) as iy:
                    with cdlt.loop(IW) as ix:
                        with cdlt.loop(N) as n:
                            with cdlt.loop(C) as c:
                                cdlt.transfer(data, ["DRAM", "VMEM1"])
                                cdlt.transfer(out, ["DRAM", "VMEM2"])
                                out.set_write_destination("VMEM2")
                                cdlt.compute("ADD", [data[n, c, iy, ix], out[n, c, oy, ox]],
                                             [out[n, c, oy, ox]], target="SIMD")
                                cdlt.compute("MUL", [out[n, c, oy, ox], denom_op],
                                             [out[n, c, oy, ox]],
                                             target="SIMD")
                        cdlt.transfer(out, ["VMEM2", "DRAM"])
        cdlt.configure("end", "SIMD")
    cdlt = add_simd_constraint(hag, cdlt, "C")
    cdlt = add_simd_tile_constraint(hag, cdlt, ["OH", "OW", "IH", "IW"])

    return cdlt


def softmax(hag):
    with CodeletTemplate("softmax") as cdlt:
        N = cdlt.dummy_op("N", cdlt.node.inputs[0].shape[0])
        C = cdlt.dummy_op("C", cdlt.node.inputs[0].shape[1])

        data = cdlt.create_operand_template("data", OP_DTYPES, [N, C], default_dtype=OP_DTYPES[2])
        out = cdlt.create_operand_template("out", OP_DTYPES, [N, C], default_dtype=OP_DTYPES[2])

        simd_size = cdlt.dummy_op("SIMD_SIZE", cdlt.hag.all_subgraph_nodes['SIMD'].dimensions[0])
        cdlt.set_inputs([data])
        cdlt.set_inputs([out])


        cdlt.configure("start", "SIMD")
        ln2 = create_immediate_with_operand(cdlt, 0, np.log(2), simd_size=simd_size)
        inv_ln2 = create_immediate_with_operand(cdlt, 1, -1/np.log(2), simd_size=simd_size)
        imm2 = create_immediate_with_operand(cdlt, 2, 1.353, simd_size=simd_size)
        imm3 = create_immediate_with_operand(cdlt, 3, 0.3585, simd_size=simd_size)
        imm4 = create_immediate_with_operand(cdlt, 4, 0.344, simd_size=simd_size)
        powimm = create_immediate_with_operand(cdlt, 5, 2, simd_size=simd_size)
        min_val, _ = range_from_cfg(FXP_CONFIGS[str(OP_DTYPES[2])])
        cdlt.configure("start", "IMM", immediate_value=min_val, index=5)

        # Max reduce output
        mx = cdlt.create_operand_template("mx", OP_DTYPES, [N], default_dtype=OP_DTYPES[2])
        cdlt.add_temp_operand(mx)

        # Expontential temporaries
        z1 = cdlt.create_operand_template("z1", OP_DTYPES, [N], default_dtype=OP_DTYPES[2])
        cdlt.add_temp_operand(z1)

        p = cdlt.create_operand_template("p", OP_DTYPES, [N], default_dtype=OP_DTYPES[2])
        cdlt.add_temp_operand(p)

        with cdlt.loop(N) as n:
            with cdlt.loop(C) as c:
                cdlt.transfer(data, ["DRAM", "VMEM1"])
                mx.set_write_destination("VMEM2")
                cdlt.compute("MAX", [data[n, c], mx[n]], [mx[n]], target="SIMD")
                z1.set_write_destination("VMEM1")
                p.set_write_destination("VMEM2")
                cdlt.compute("MUL", [mx[n], inv_ln2], [z1[n]], target="SIMD")
                cdlt.compute("FLOOR", [z1[n]], [z1[n]], target="SIMD")
                cdlt.compute("MUL", [z1[n], ln2], [p[n]], target="SIMD")
                cdlt.compute("ADD", [data[n,c], p[n]], [p[n]], target="SIMD")
                cdlt.compute("ADD", [p[n], imm2], [p[n]], target="SIMD")
                cdlt.compute("POW", [p[n], powimm], [p[n]], target="SIMD")
                cdlt.compute("MUL", [p[n], imm3], [p[n]], target="SIMD")
                out.set_write_destination("VMEM1")
                cdlt.compute("ADD", [p[n], imm4], [out[n, c]], target="SIMD")
                cdlt.transfer(out, ["VMEM1", "DRAM"])

    cdlt = add_simd_constraint(hag, cdlt, "C")
    return cdlt

def softmax4d(hag):
    with CodeletTemplate("softmax4d") as cdlt:
        N = cdlt.dummy_op("N", cdlt.node.inputs[0].shape[0])
        C = cdlt.dummy_op("C", cdlt.node.inputs[0].shape[1])
        H = cdlt.dummy_op("H", cdlt.node.inputs[0].shape[2])
        W = cdlt.dummy_op("W", cdlt.node.inputs[0].shape[3])

        data = cdlt.create_operand_template("data", OP_DTYPES, [N, C, H, W], default_dtype=OP_DTYPES[2])
        out = cdlt.create_operand_template("out", OP_DTYPES, [N, C, H, W], default_dtype=OP_DTYPES[2])

        simd_size = cdlt.dummy_op("SIMD_SIZE", cdlt.hag.all_subgraph_nodes['SIMD'].dimensions[0])
        cdlt.set_inputs([data])
        cdlt.set_outputs([out])


        cdlt.configure("start", "SIMD")
        aval = create_immediate_with_operand(cdlt, np.log(2), simd_size=simd_size, cast_float_to_fxp=True)
        bval = create_immediate_with_operand(cdlt, -1/np.log(2), simd_size=simd_size, cast_float_to_fxp=True)
        cval = create_immediate_with_operand(cdlt, 1.353, simd_size=simd_size, cast_float_to_fxp=True)
        dval = create_immediate_with_operand(cdlt, 0.3585, simd_size=simd_size, cast_float_to_fxp=True)
        eval = create_immediate_with_operand(cdlt, 0.344, simd_size=simd_size, cast_float_to_fxp=True)
        zero = create_immediate_with_operand(cdlt, 0, simd_size=simd_size)
        min_val, _ = range_from_cfg(FXP_CONFIGS[str(OP_DTYPES[2])])
        cdlt.configure("start", "IMM", immediate_value=min_val, index=len(cdlt.temps))

        min_op = cdlt.create_temp_operand([simd_size], "IMM")
        # Max reduce output
        mx = cdlt.create_operand_template("mx", OP_DTYPES, [N, C, W], default_dtype=OP_DTYPES[2])
        cdlt.add_temp_operand(mx)

        # Expontential temporaries
        z1 = cdlt.create_operand_template("z1", OP_DTYPES, [N, C, H, W], default_dtype=OP_DTYPES[2])
        cdlt.add_temp_operand(z1)

        y = cdlt.create_operand_template("y", OP_DTYPES, [N, C, H, W], default_dtype=OP_DTYPES[2])
        cdlt.add_temp_operand(y)
        with cdlt.loop(H) as h:
            with cdlt.loop(N) as n:
                with cdlt.loop(C) as c:
                    with cdlt.loop(W) as w:
                        cdlt.transfer(data, ["DRAM", "VMEM1"])
                        mx.start_location = "VMEM2"
                        mx.set_write_destination("VMEM2")
                        out.set_write_destination("VMEM1")
                        z1.set_write_destination("VMEM1")
                        y.set_write_destination("VMEM2")

                        # First, do compute max and then subtract
                        cdlt.compute("MOVE", [min_op], [mx[n, c, w]], target="SIMD")
                        cdlt.compute("MAX", [data[n, c, h, w], mx[n, c, w]], [mx[n, c, w]], target="SIMD")
                        cdlt.compute("SUB", [data[n,c,h,w], mx[n, c, w]], [out[n,c,h,w]], target="SIMD")

                        # Now, Comptue exp
                        cdlt.compute("MUL", [out[n,c,h,w], bval], [y[n, c, h, w]], target="SIMD")
                        cdlt.compute("FLOOR", [y[n, c, h, w]], [y[n, c, h, w]], target="SIMD")
                        cdlt.compute("MUL", [y[n,c,h,w], aval], [y[n,c,h,w]], target="SIMD")
                        cdlt.compute("ADD", [out[n,c, h, w], y[n, c, h, w]], [out[n,c,h,w]], target="SIMD")
                        cdlt.compute("ADD", [out[n, c, h, w], cval], [out[n,c,h, w]], target="SIMD")

                        cdlt.compute("MOVE", [out[n,c,h,w]], [y[n, c, h, w]], target="SIMD")
                        cdlt.compute("MUL", [out[n,c,h,w], y[n,c,h,w]], [out[n, c, h, w]], target="SIMD")

                        cdlt.compute("MUL", [out[n,c,h,w], dval], [out[n, c, h, w]], target="SIMD")
                        cdlt.compute("ADD", [out[n,c,h,w], eval], [out[n, c, h, w]], target="SIMD")

                        # Next, compute sum for denominator
                        cdlt.compute("MOVE", [zero], [mx[n, c, w]], target="SIMD")
                        cdlt.compute("ADD", [out[n,c,h,w], mx[n,c,w]], [mx[n, c, w]], target="SIMD")


                        cdlt.transfer(out, ["VMEM1", "DRAM"])

    cdlt = add_simd_constraint(hag, cdlt, "W")
    cdlt = add_simd_tile_constraint(hag, cdlt, ["H"])
    return cdlt

def gelu(hag):
    with CodeletTemplate('gelu') as cdlt:
        B = cdlt.dummy_op("B", cdlt.node.inputs[0].shape[0])
        M = cdlt.dummy_op("M", cdlt.node.inputs[0].shape[1])
        P = cdlt.dummy_op("P", cdlt.node.inputs[0].shape[2])

        data = cdlt.create_operand_template("data", OP_DTYPES, [B, M, P], default_dtype=OP_DTYPES[2])
        cdlt.set_inputs([data])
        out = cdlt.create_operand_template("out", OP_DTYPES, [B, M, P], default_dtype=OP_DTYPES[0])
        cdlt.set_outputs([out])
        sign_val = cdlt.create_operand_template("sign_val", OP_DTYPES, [B, M, P], default_dtype=OP_DTYPES[2])
        cdlt.add_temp_operand(sign_val)

        gelu_out = cdlt.create_operand_template("gelu_out", OP_DTYPES, [B, M, P], default_dtype=OP_DTYPES[2])
        gelu_out.start_location = "VMEM2"
        cdlt.add_temp_operand(gelu_out)

        simd_size = cdlt.dummy_op("SIMD_SIZE", cdlt.hag.all_subgraph_nodes['SIMD'].dimensions[0])
        cdlt.configure('start', 'SIMD')
        b_s = create_immediate_with_operand(cdlt, -1.769 / QUANT_SCALE, simd_size=simd_size, cast_float_to_fxp=True)
        aop = create_immediate_with_operand(cdlt, -0.2888, simd_size=simd_size, cast_float_to_fxp=True)
        bop = create_immediate_with_operand(cdlt, -1.769, simd_size=simd_size, cast_float_to_fxp=True)
        cop = create_immediate_with_operand(cdlt, 1, simd_size=simd_size)
        s_f = create_immediate_with_operand(cdlt, QUANT_SCALE, simd_size=simd_size)
        m0 = create_immediate_with_operand(cdlt, QUANT_SCALE, simd_size=simd_size)
        nshift = create_immediate_with_operand(cdlt, SIGN_SHIFT, simd_size=simd_size)
        with cdlt.loop(P) as p:
            with cdlt.loop(B) as b:
                with cdlt.loop(M) as m:
                    cdlt.transfer(data, ["DRAM", "VMEM1"])
                    out.set_write_destination('VMEM1')
                    sign_val.set_write_destination("VMEM1")
                    gelu_out.set_write_destination("VMEM2")
                    indices = (b, m, p)

                    cdlt.compute("ABS", [data[indices]], [gelu_out[indices]],
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
                    cdlt.compute("SIGN", [data[indices]], [sign_val[indices]],
                                 target="SIMD")

                    cdlt.compute("MUL", [gelu_out[indices], sign_val[indices]], [gelu_out[indices]],
                                 target="SIMD")
                    cdlt.compute("ADD", [gelu_out[indices], m0], [gelu_out[indices]], target="SIMD")
                    cdlt.compute("MUL", [data[indices], gelu_out[indices]], [out[indices]], target="SIMD")
                    cdlt.compute("MUL", [out[indices], s_f], [out[indices]], target="SIMD")

                    add_scale_and_cast_op(cdlt, out, out, m0, nshift, indices)

                    cdlt.transfer(out, ["VMEM1", "DRAM"])
        cdlt.configure('end', 'SIMD')
    cdlt = add_simd_constraint(hag, cdlt, "P")
    return cdlt

DNN_CDLTS = {
    "avg_pool": averagepool2d,
    "softmax4d": softmax4d,
    "batch_norm": batch_norm,
    "cross_entropy_loss": cross_entropy_loss,
    "depthwise_conv": depthwise_conv,
    "depthwise_conv_bias": depthwise_conv_bias,
    "global_avg_pool": global_avg_pool,
    "max_pool": maxpool2d,
    "mean_var": mean_var,
    "gelu": gelu,
}