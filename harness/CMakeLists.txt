cmake_minimum_required(VERSION 3.22)
project(onnx_schema_fuzz_harness CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(SAN_FLAGS "-fsanitize=address,undefined -fno-omit-frame-pointer" CACHE STRING "Sanitizer flags")
option(BUILD_LIBFUZZER "Build the libFuzzer target (requires LLVM clang)" OFF)

# An ONNX install configured with -DONNX_USE_ASAN=ON lists its private
# Sanitizer::address/undefined targets in ONNXTargets.cmake without exporting
# them. Sanitizer flags come from SAN_FLAGS below, so empty stand-ins suffice.
foreach(san address undefined)
  if(NOT TARGET Sanitizer::${san})
    add_library(Sanitizer::${san} INTERFACE IMPORTED)
  endif()
endforeach()

find_package(ONNX CONFIG REQUIRED)

separate_arguments(SAN_LIST UNIX_COMMAND "${SAN_FLAGS}")

add_library(osf_target STATIC target.cc)
target_link_libraries(osf_target PUBLIC ONNX::onnx ONNX::onnx_proto)
target_compile_definitions(osf_target PUBLIC ONNX_NAMESPACE=onnx ONNX_ML=1)
target_compile_options(osf_target PUBLIC ${SAN_LIST})
target_link_options(osf_target PUBLIC ${SAN_LIST})

add_executable(onnx_driver driver.cc)
target_link_libraries(onnx_driver PRIVATE osf_target)

if(BUILD_LIBFUZZER)
  add_executable(fuzz_shape_inference fuzz_shape_inference.cc)
  target_link_libraries(fuzz_shape_inference PRIVATE osf_target)
  target_link_options(fuzz_shape_inference PRIVATE -fsanitize=fuzzer)
endif()
