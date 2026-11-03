"""Unrecovered v1 parity evidence; separate from fresh-build J0 F1 acceptance."""
import unittest


class DeferredPortParityTests(unittest.TestCase):
    @unittest.skip('[NEEDS VERIFY] Signed historical telemetry/expected-output replay bundle not recovered')
    def test_historical_gate_replay(self):
        pass

    @unittest.skip('[NEEDS VERIFY] J1 v1 PyTorch checkpoint/expansion fixture not recovered; analytic center fixture covered separately')
    def test_v1_expansion_frozen_tensor_parity(self):
        pass
