const { OTLPTraceExporter } = require('@opentelemetry/exporter-trace-otlp-http');
const exporter = new OTLPTraceExporter({
  url: 'https://us.cloud.langfuse.com/api/public/otel/v1/traces',
  headers: {
    'Authorization': 'Basic cGstbGYtMGUzZjgyOGQtZTlmNC00NDU0LThlYzYtNmVlYjdkOGQ1MzI0OnNrLWxmLTFkNzNjMDVhLThkMTktNDA3ZC1hMWJiLWY4ODU2ZjNlMDdmNQ=='
  }
});
exporter.export([{
  resource: { attributes: {} },
  instrumentationLibrary: { name: 'test' },
  name: 'test-span',
  kind: 0,
  traceId: '12345678901234567890123456789012',
  spanId: '1234567890123456',
  startTime: [0, 0],
  endTime: [0, 0],
  status: { code: 0 },
  attributes: {}
}], (res) => {
  console.log('Result:', res);
});
