{
  python,
  gitUpdater,
  lib,
  stdenv,
}:
let
  version = "1.2";
  name = "uiina";
in
stdenv.mkDerivation {
  pname = name;
  inherit version;

  src = ./.;

  nativeBuildInputs = [
    (python.withPackages (
      pypkgs: with pypkgs; [
        shiv
      ]
    ))
  ];
  buildPhase = ''
    runHook preBuild

    shiv --reproducible \
         --compressed \
         --compile-pyc \
         --output-file uiina.pyz \
         --console-script uiina \
         .

    runHook postBuild
  '';

  installPhase = ''
    runHook preInstall

    mkdir -p $out/bin
    cp uiina.pyz $out/bin/uiina
    chmod +x $out/bin/uiina

    runHook postInstall
  '';

  # https://wiki.nixos.org/w/index.php?title=Nixpkgs/Update_Scripts
  passthru.updateScript = gitUpdater { };

  meta = {
    license = lib.licenses.gpl2;
    mainProgram = "uiina";
    homepage = "https://github.com/ed9w2in6/uiina";
    description = "Using single-instance of IINA when launching through the command line";
    platforms = lib.platforms.darwin;
    # maintainers = with lib.maintainers; [];
    sourceProvenance = [ lib.sourceTypes.fromSource ];
  };
}
