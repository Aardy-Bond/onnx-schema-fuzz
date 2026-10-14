#pragma once

#include <cstddef>
#include <cstdint>

namespace osf {

// Outcome of running one serialized ModelProto through the target.
// Sanitizer-detected defects do not return: the process aborts with a report.
enum class Outcome {
  kParseFailed,  // not a wire-valid ModelProto; uninteresting
  kRejected,     // ONNX raised a ValidationError/InferenceError: the defined, safe behaviour
  kAccepted,     // inference and checking completed without error
};

// Parses `data` as an onnx.ModelProto, runs type/shape inference with default
// options, again with data propagation enabled, then the full model checker.
Outcome RunTarget(const uint8_t* data, size_t size);

const char* OutcomeName(Outcome outcome);

}  // namespace osf
