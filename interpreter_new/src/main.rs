fn main() {
    let args: Vec<String> = std::env::args().collect();

    if args.len() != 2 {
        println!("Usage: meda <file_path>");
        return;
    }

    let file_path = &args[1];

    print!("Reading file: {}", file_path);
}
