/* Measurement only; internal x265 3.5 interfaces, no public ABI changes. */
#ifndef X265_PRISM_TELEMETRY_H
#define X265_PRISM_TELEMETRY_H
#include "frame.h"
#include "ratecontrol.h"
namespace X265_NS {
void prismTelemetryFrame(const Frame&, const x265_param&, const RateControlEntry&, int);
void prismTelemetryCUs(const Frame&, const x265_param&);
}
#endif
