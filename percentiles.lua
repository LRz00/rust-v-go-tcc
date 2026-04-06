-- Custom percentile output for wrk benchmark parsing.
done = function(summary, latency, requests)
  io.write("P95: " .. latency:percentile(95) .. "\n")
  io.write("P99: " .. latency:percentile(99) .. "\n")
end
