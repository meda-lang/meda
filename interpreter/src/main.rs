fn main() {
    let args: Vec<String> = std::env::args().collect();
    dbg!(args);
    let file_path = &args[1];
    print!("Reading file: {}", file_path);
}
