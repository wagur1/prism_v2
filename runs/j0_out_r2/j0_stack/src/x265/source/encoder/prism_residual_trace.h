/*
 * x265_prism_residual_v1 -- best-effort x265 tag 3.5 / 8-bit instrumentation.
 *
 * Audited insertion-site rationale (source/build verification still pending):
 * source/encoder/frameencoder.cpp, FrameEncoder::getEncodedPicture(), immediately
 * after m_done.wait(), before m_frame is released to Encoder. The completed
 * FrameData contains the winning CUData, including m_qp after AQ/quantOffsets,
 * legal-QP clipping, checkDQP/setQPSubCUs and any VBV row re-encode. Read that
 * committed state, not an RDO candidate in Analysis::compressCTU/calculateQpforCuSize.
 * Follow the offsets producer in source/encoder/slicetype.cpp (AQ) and
 * source/common/lowres.cpp; neither is a final residual-QP observation site.
 * No QP or bitstream state is changed. Review gate0/PATCH_AUDIT.md against 3.5.
 *
 * One CSV row per final leaf CU: input PTS, luma pixel origin, stored luma QP,
 * OR of all component/TU coded-block flags, and CU skip flag.
 * The caller must keep PRISM_X265_QP_TRACE stable until all encoders drain.
 * A fresh path is required for each encode. Unset/empty env: no trace file I/O,
 * no CTU traversal and no mutex acquisition. The env lookup is once per frame.
 * Ubuntu's pthread mutex serializes complete frames, including flush and close.
 */
#ifndef X265_PRISM_RESIDUAL_TRACE_H
#define X265_PRISM_RESIDUAL_TRACE_H

#include "common.h"
#include "frame.h"
#include "framedata.h"
#include "cudata.h"
#include "constants.h"
#include <stdio.h>
#include <stdlib.h>
#if X265_DEPTH == 8
#include "threading.h"
#endif

namespace X265_NS {
static Lock prismResidualMutex;
static void x265_prism_residual_v1(const Frame& frame, const x265_param& param)
{
#if X265_DEPTH == 8
    const char* path = getenv("PRISM_X265_QP_TRACE");
    if (!path || !path[0])
        return;
    // This header is included ONLY by frameencoder.cpp: one mutex per library.
    ScopedLock traceLock(prismResidualMutex);
    FILE* trace = fopen(path, "a");
    if (!trace)
    {
        perror("x265_prism_residual_v1: fopen");
        return; // Missing/incomplete evidence must fail the external gate.
    }
    bool failed = fseek(trace, 0, SEEK_END) != 0;
    long end = ftell(trace);
    if (end < 0)
        failed = true;
    if (!failed && end == 0)
        failed = fprintf(trace, "frame,x,y,qp,has_residual,skip\n") < 0;

    const uint32_t cols = (param.sourceWidth + param.maxCUSize - 1) / param.maxCUSize;
    const uint32_t rows = (param.sourceHeight + param.maxCUSize - 1) / param.maxCUSize;
    for (uint32_t addr = 0; !failed && addr < cols * rows; ++addr)
    {
        const CUData* ctu = frame.m_encData->getPicCTU(addr);
        // CU arrays use Morton/Z-scan indexing at the minimum partition size.
        for (uint32_t part = 0; part < ctu->m_numPartitions;)
        {
            const uint32_t x = ctu->m_cuPelX + g_zscanToPelX[part];
            const uint32_t y = ctu->m_cuPelY + g_zscanToPelY[part];
            if (x >= (uint32_t)param.sourceWidth || y >= (uint32_t)param.sourceHeight)
            {
                ++part; // Padding partitions may have no initialized CU depth.
                continue;
            }
            const uint32_t depth = ctu->m_cuDepth[part];
            const uint32_t count = depth < 16 ? ctu->m_numPartitions >> (2 * depth) : 0;
            if (!count || part + count > ctu->m_numPartitions)
            {
                fprintf(stderr, "x265_prism_residual_v1: invalid leaf partition\n");
                failed = true;
                break;
            }
            bool residual = false;
            // OR every TU's CBF bitmask; looking only at the first TU loses AC/
            // chroma-only residual in split transforms. Include all TU depths.
            for (uint32_t p = part; p < part + count; ++p)
            {
                residual |= ctu->m_cbf[0][p] != 0;
                if (param.internalCsp != X265_CSP_I400)
                    residual |= (ctu->m_cbf[1][p] | ctu->m_cbf[2][p]) != 0;
            }
            if (fprintf(trace, "%lld,%u,%u,%d,%d,%d\n",
                        (long long)frame.m_pts, x, y, (int)ctu->m_qp[part],
                        residual ? 1 : 0, ctu->isSkipped(part) ? 1 : 0) < 0)
                failed = true;
            part += count;
        }
    }
    if (fflush(trace) != 0)
        failed = true;
    if (fclose(trace) != 0)
        failed = true;
    if (failed)
        fprintf(stderr, "x265_prism_residual_v1: incomplete trace frame %lld\n",
                (long long)frame.m_pts);
#else
    (void)frame;
    (void)param;
#endif
}
} // namespace X265_NS
#endif
