// Persistent cooperative CUDA LIF kernel. mV, ms; double precision state/weights.
// One grid launch per chunk. Two grid barriers per tick, no host tick loop.
#include <cooperative_groups.h>
namespace cg = cooperative_groups;

// Random123 Philox4x32-10. Counter identifies (neuron, tick), not batch position;
// paired conditions share input streams without sharing their evolving state.
__device__ double uniform(unsigned neuron, unsigned tick, unsigned seed, int stream) {
    unsigned x = neuron, y = tick, z = 0, w = 0;
    unsigned k0 = seed, k1 = 0xdecafbadU;
    for (int r = 0; r < 10; ++r) {
        unsigned hi0 = __umulhi(0xD2511F53U, x), lo0 = 0xD2511F53U * x;
        unsigned hi1 = __umulhi(0xCD9E8D57U, z), lo1 = 0xCD9E8D57U * z;
        unsigned a = hi1 ^ y ^ k0, b = hi0 ^ w ^ k1;
        x = a; y = lo1; z = b; w = lo0;
        k0 += 0x9E3779B9U; k1 += 0xBB67AE85U;
    }
    // Open (0,1), 32-bit uniform. Separate words for bg and extended input.
    return ((stream == 0 ? x : z) + 0.5) * 0x1p-32;
}

extern "C" __global__ void advance(
    double* v, double* g, double* incoming, int* last,
    const double* threshold, const double* gain, const double* bg,
    const double* rates, const unsigned char* keep, const unsigned* seeds,
    const int* offsets, const int* post, const double* weights,
    int* ring_ids, int* ring_counts, int* counts, int* hist, int* first,
    int* spike_ticks, const int* bg_event_index, const unsigned char* bg_events,
    int bg_event_width, int bg_event_start,
    int record, int n, int batch, int ring, int capacity,
    int tick0, int steps, int ticks_per_ms, int refractory,
    double dv, double dg, double coupling, double v0, double reset,
    int bg_n, double bg_p, double bg_p0, double dt_s, double ext_weight) {
    cg::grid_group grid = cg::this_grid();
    __shared__ int found;
    const int tid = threadIdx.x, block = blockIdx.x;
    const int stride = gridDim.x * blockDim.x, total = n * batch;
    const int warp = tid / 32, lane = tid % 32, warps = blockDim.x / 32;
    for (int step = 0; step < steps; ++step) {
        const int tick = tick0 + step, slot = tick % ring;
        const int own = (slot * gridDim.x + block) * capacity;
        if (tid == 0) found = 0;
        __syncthreads();
        for (int j = block * blockDim.x + tid; j < total; j += stride) {
            int b = j / n, i = j % n;
            double oldg = g[j] + incoming[j];
            incoming[j] = 0;
            bool active = tick - last[j] >= refractory;
            double vn = v[j], gn = oldg;
            if (active) {
                vn = v0 + (vn - v0) * dv + oldg * coupling;
                gn = oldg * dg;
            }
            bool fire = active && vn > threshold[j];
            if (fire) {
                vn = reset; gn = 0;
                last[j] = tick;
                int k = counts[j]++;
                if (k == 0) first[j] = tick;
                if (record) spike_ticks[k * total + j] = tick;
                atomicAdd(hist + b * (steps / ticks_per_ms) + step / ticks_per_ms, 1);
                ring_ids[own + atomicAdd(&found, 1)] = j;
            } else if (active) {
                // Brian's conditional-write g rejects arrivals in refractory.
                if (bg_event_width) {
                    int target = bg_event_index[i];
                    if (target >= 0)
                        gn += bg_events[(long long)(tick - bg_event_start) * bg_event_width + target] * bg[i];
                } else if (bg[i] != 0) {
                    double u = uniform(i, tick, seeds[b], 0), p = bg_p0;
                    double cdf = p;
                    int k = 0;
                    while (u > cdf && k < bg_n) {
                        ++k;
                        p *= (bg_n - k + 1) * bg_p / (k * (1 - bg_p));
                        cdf += p;
                    }
                    gn += k * bg[i];
                }
                if (rates[j] > 0 && uniform(i, tick, seeds[b], 1) < rates[j] * dt_s)
                    gn += ext_weight;
            }
            v[j] = vn; g[j] = gn;
        }
        __syncthreads();
        if (tid == 0) ring_counts[slot * gridDim.x + block] = found;
        grid.sync();  // all neuron states and spike lists published; incoming cleared
        int delayed = (tick + 1) % ring;  // ring = delay + 1
        int num = ring_counts[delayed * gridDim.x + block];
        int base = (delayed * gridDim.x + block) * capacity;
        for (int s = warp; s < num; s += warps) {
            int src = ring_ids[base + s], b = src / n, pre = src % n;
            if (!keep[src]) continue;
            int end = offsets[pre + 1];
            for (int e = offsets[pre] + lane; e < end; e += 32) {
                int dst = b * n + post[e];
                // Thresholding already set last=t on firing cells. For zero
                // refractory they still reject input on the firing tick.
                if (last[dst] != tick && tick - last[dst] >= refractory)
                    atomicAdd(incoming + dst, weights[e] * gain[dst]);
            }
        }
        grid.sync();  // arrivals complete before next update; list slot safe to reuse
    }
}
