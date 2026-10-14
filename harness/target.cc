#include "target.h"

#include <cstdio>
#include <cstdlib>
#include <exception>

#include "onnx/checker.h"
#include "onnx/defs/schema.h"
#include "onnx/proto_utils.h"
#include "onnx/shape_inference/implementation.h"

namespace osf {

namespace {

// Default options match what onnx.shape_inference.infer_shapes() uses from Python,
// so a crash on this pass is reachable from the most common entry point.
const onnx::ShapeInferenceOptions kDefaultOptions{/*check_type=*/false, /*strict_mode=*/0, /*data_prop=*/false};
const onnx::ShapeInferenceOptions kDataPropOptions{/*check_type=*/true, /*strict_mode=*/0, /*data_prop=*/true};

// OSF_VERBOSE=1 prints why a model was rejected (off in fuzzing: it is slow and noisy).
bool Verbose() {
  static const bool verbose = [] {
    const char* v = std::getenv("OSF_VERBOSE");
    return v != nullptr && v[0] == '1';
  }();
  return verbose;
}

void Report(const char* stage, const std::exception& e) {
  if (Verbose()) {
    std::fprintf(stderr, "[%s] %s\n", stage, e.what());
  }
}

}  // namespace

Outcome RunTarget(const uint8_t* data, size_t size) {
  onnx::ModelProto model;
  if (!onnx::ParseProtoFromBytes(&model, reinterpret_cast<const char*>(data), size)) {
    return Outcome::kParseFailed;
  }

  bool rejected = false;
  for (const auto* options : {&kDefaultOptions, &kDataPropOptions}) {
    onnx::ModelProto copy = model;
    try {
      onnx::shape_inference::InferShapes(copy, onnx::OpSchemaRegistry::Instance(), *options);
    } catch (const std::exception& e) {
      Report(options == &kDefaultOptions ? "infer_shapes" : "infer_shapes+data_prop", e);
      rejected = true;
    }
  }

  try {
    onnx::checker::check_model(model, /*full_check=*/true);
  } catch (const std::exception& e) {
    Report("check_model", e);
    rejected = true;
  }

  return rejected ? Outcome::kRejected : Outcome::kAccepted;
}

const char* OutcomeName(Outcome outcome) {
  switch (outcome) {
    case Outcome::kParseFailed:
      return "parse_failed";
    case Outcome::kRejected:
      return "rejected";
    case Outcome::kAccepted:
      return "accepted";
  }
  return "unknown";
}

}  // namespace osf
