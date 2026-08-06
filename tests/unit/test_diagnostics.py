from cexlatency.diagnostics import _parse_windows_adapters, summarize_route


def test_windows_route_summary_extracts_hops_and_bottleneck():
    output="""Tracing route
      1    <1 ms    1 ms    <1 ms  192.168.1.1
      2     8 ms    9 ms     8 ms  10.0.0.1
      3    45 ms   43 ms    44 ms  203.0.113.5
      4     *       *        *     Request timed out.
    """
    result=summarize_route(output)
    assert result["hop_count"] == 4
    assert result["responding_hops"] == 3
    assert result["suspected_bottleneck_hop"] == 3
    assert result["largest_hop_increase_ms"] > 30
    assert result["route_fingerprint"]


def test_linux_route_summary_handles_fractional_latency():
    output="""traceroute to example.test
     1  192.168.1.1  0.321 ms  0.400 ms  0.500 ms
     2  198.51.100.2  12.100 ms  11.900 ms  12.000 ms
    """
    result=summarize_route(output)
    assert result["hop_count"] == 2
    assert result["max_hop_latency_ms"] == 12
    assert result["suspected_bottleneck_hop"] is None


def test_windows_adapter_parser_excludes_virtual_interfaces():
    output='[{"Name":"Ethernet","InterfaceDescription":"Intel NIC","HardwareInterface":true,"Virtual":false},{"Name":"Tailscale","InterfaceDescription":"Tunnel","HardwareInterface":false,"Virtual":true}]'
    assert _parse_windows_adapters(output) == ["Ethernet [Intel NIC]"]
