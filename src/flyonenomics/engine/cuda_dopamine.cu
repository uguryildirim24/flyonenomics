// Literal float64 port of neuromod/pools.py and receptors.py; no fast math.
extern "C" __global__ void pools(
    double* da, const int* counts, const int* ptr, const int* idx, const double* m,
    const double* alpha, const double* source, const double* vmax, const double* km,
    const double* rel, const unsigned char* mask, const unsigned char* clamped,
    int n, int nc, int batch, double dt, double kns, double ref) {
    int j = blockIdx.x * blockDim.x + threadIdx.x;
    if (j >= batch * nc) return;
    int b = j / nc, c = j % nc;
    if (clamped[b] || !mask[c]) { da[j] = ref; return; }
    double count = 0;
    for (int e = ptr[c]; e < ptr[c+1]; ++e) count += m[e] * counts[b*n + idx[e]];
    double old = da[j];
    double release = rel[b] * (alpha[j] * count + source[j] * dt);
    double clear = vmax[j] * old / (km[j] + old) + kns * old;
    da[j] = fmax(0., old + release - clear * dt);
}

extern "C" __global__ void compose(
    const double* da, double* threshold, double* gain,
    const int* ptr, const int* idx, const double* w, const unsigned char* exposed,
    const double* r1, const double* r2, const double* base, const double* shift,
    const double* geno_gain, const unsigned char* silenced, const unsigned char* enabled,
    int n, int nc, int batch, double kd1, double kd2, double dv1, double dv2,
    double gamma1, double gamma2, double thlo, double thhi, double glo, double ghi,
    double silence_threshold) {
    int j = blockIdx.x * blockDim.x + threadIdx.x;
    if (j >= batch * n) return;
    int b = j / n, i = j % n;
    double dv = 0., gda = 1.;
    if (enabled[b]) {
        double di = 0.;
        for (int e = ptr[i]; e < ptr[i+1]; ++e) di += w[e] * da[b*nc + idx[e]];
        double occ1 = di / (di + kd1) * exposed[i];
        double occ2 = di / (di + kd2) * exposed[i];
        dv = -dv1 * r1[j] * occ1 + dv2 * r2[j] * occ2;
        gda = 1. + gamma1 * r1[j] * occ1 - gamma2 * r2[j] * occ2;
    }
    double th = fmin(thhi, fmax(thlo, base[j] + shift[j] + dv));
    threshold[j] = silenced[j] ? silence_threshold : th;
    gain[j] = fmin(ghi, fmax(glo, geno_gain[j] * gda));
}
