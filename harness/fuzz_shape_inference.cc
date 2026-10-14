// libFuzzer entry point. Built only when BUILD_LIBFUZZER=1 (needs LLVM clang).
#include <cstddef>
#include <cstdint>

#include "target.h"

extern "C" int LLVMFuzzerTestOneInput(const uint8_t* data, size_t size) {
  osf::RunTarget(data, size);
  return 0;
}
