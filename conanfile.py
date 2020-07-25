from conans import ConanFile, tools
import os
import sys


class TensorFlowConan(ConanFile):
    name = "tensorflow"
    version = "2.2.0"
    description = "https://www.tensorflow.org/"
    topics = ("conan", "tensorflow", "ML")
    url = "https://github.com/bincrafters/conan-tensorflow"
    homepage = "The core open source library to help you develop and train ML models"
    license = "Apache-2.0"
    settings = "os", "arch", "compiler", "build_type"
    options = {"shared": [True, False], "fPIC": [True, False]}
    default_options = {"shared": False, "fPIC": True}
    exports = ["config.patch"]

    @property
    def _source_subfolder(self):
        return os.path.join(self.source_folder, "source_subfolder")

    def build_requirements(self):
        if not tools.which("bazel"):
            self.build_requires("bazel_installer/0.27.1@bincrafters/stable")

    def config_options(self):
        if self.settings.os == 'Windows':
            del self.options.fPIC

    def source(self):
        source_url = "https://github.com/tensorflow/tensorflow"
        tools.get("{0}/archive/v{1}.tar.gz".format(source_url, self.version),
            sha256="69cd836f87b8c53506c4f706f655d423270f5a563b76dc1cfa60fbc3184185a3")
        extracted_dir = self.name + "-" + self.version
        os.rename(extracted_dir, self._source_subfolder)
        tools.patch(patch_file="config.patch", base_path=self._source_subfolder)

    @property 
    def _latest_vc_compiler_version(self):
        if self.settings.compiler != "Visual Studio":
            return "0"
        vs = tools.vswhere(latest=True)
        self.output.info("VS compiler version: {}".format(vs[0]["installationVersion"]))
        vs_version = tools.Version(vs[0]["installationVersion"])
        return "{}.{}".format(vs_version.major, vs_version.minor)

    @property
    def _tf_compiler_vars(self):
        tf_vars = {}
        if self.settings.compiler == "clang":
            tf_vars["CC"] = tools.which("clang")
            tf_vars["CC_OPT_FLAGS"] = "-march=native"

        elif self.settings.compiler == "Visual Studio":   
            # this doesn't appear to be reliable. Works locally but not on CI
            # tf_vars["TF_VC_VERSION"] = self._latest_vc_compiler_version
            tf_vars["TF_OVERRIDE_EIGEN_STRONG_INLINE"] = "1"
            tf_vars["CC_OPT_FLAGS"] = "/arch:AVX"

        return tf_vars

    @property
    def _tf_compiler_args(self):
        tf_args = []
        tf_args.append("-s") # diagnostic
        if self.settings.compiler == "clang":
            tf_args.append("--cxxopt=-xc++")
            if self.settings.compiler.libcxx == "libc++":
                tf_args.append("--copt=-stdlib=libc++")

        return tf_args

    def build(self):
        with tools.chdir(self._source_subfolder):
            env_build = {
                "PYTHON_BIN_PATH": sys.executable,
                "USE_DEFAULT_PYTHON_LIB_PATH": "1",
                "TF_ENABLE_XLA": '0',
                "TF_NEED_OPENCL_SYCL": '0',
                "TF_NEED_ROCM": '0',
                "TF_NEED_CUDA": '0',
                "TF_NEED_MPI": '0',
                "TF_DOWNLOAD_CLANG": '0',
                "TF_SET_ANDROID_WORKSPACE": "0",
                "TF_CONFIGURE_IOS": "1" if self.settings.os == "iOS" else "0"
            }
            env_build.update(self._tf_compiler_vars)
            self.output.info("Tensorflow env: ")
            self.output.info(env_build)
            with tools.environment_append(env_build):
                self.run("python configure.py" if tools.os_info.is_windows else "./configure")
                command_args = ["--config=opt"]
                command_args += self._tf_compiler_args

                command_line = "bazel build " + " ".join(command_args) + " "
                self.output.info("Running tensorflow build: ")
                self.output.info(command_line)
                self.run(command_line + "%s --verbose_failures" % "//tensorflow:tensorflow_cc")
                self.run(command_line + "%s --verbose_failures" % "//tensorflow:tensorflow_cc_dll_import_lib")
                self.run(command_line + "%s --verbose_failures" % "//tensorflow:install_headers")
                self.run("bazel shutdown")

    def package(self):
        self.copy(pattern="LICENSE", dst="licenses", src=self._source_subfolder)
        self.copy(pattern="*.dll", dst="bin", src=self._source_subfolder, keep_path=False, symlinks=True)
        self.copy(pattern="*.lib", dst="lib", src=self._source_subfolder, keep_path=False, symlinks=True)
        self.copy(pattern="*.so*", dst="lib", src=self._source_subfolder, keep_path=False, symlinks=True)
        self.copy(pattern="*.dylib*", dst="lib", src=self._source_subfolder, keep_path=False, symlinks=True)

    def package_info(self):
        self.cpp_info.libs = tools.collect_libs(self)
