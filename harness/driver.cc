// Runs each model file given on the command line through the target and prints
// one line per file. Used for smoke tests, crash reproduction, and corpus replay
// on toolchains without libFuzzer (e.g. Apple clang).
#include <cstdio>
#include <fstream>
#include <iterator>
#include <string>

#include "target.h"

int main(int argc, char** argv) {
  if (argc < 2) {
    std::fprintf(stderr, "usage: %s model.onnx [model.onnx ...]\n", argv[0]);
    return 2;
  }
  for (int i = 1; i < argc; ++i) {
    std::ifstream in(argv[i], std::ios::binary);
    if (!in) {
      std::fprintf(stderr, "cannot open %s\n", argv[i]);
      return 2;
    }
    std::string bytes((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    auto outcome = osf::RunTarget(reinterpret_cast<const uint8_t*>(bytes.data()), bytes.size());
    std::printf("%s\t%zu bytes\t%s\n", osf::OutcomeName(outcome), bytes.size(), argv[i]);
    std::fflush(stdout);
  }
  return 0;
}
